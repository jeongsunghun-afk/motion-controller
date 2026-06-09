"""mujoco_node.py — biped_sim (2-leg HL/HR)

unitree_mujoco style ROS2 simulator node for biped robot.

Topic interface (motorcortex_bridge 와 동일):
    sub: /low_cmd          (sensor_msgs/JointState, 8-dim position/velocity/effort)
    sub: /rl_gains         (옵션: Kp/Kd 동적 갱신)
    pub: /joint_states     (50 Hz)
    pub: /low_state        (50 Hz)
    pub: /imu              (50 Hz)

Internal control flow @ 200 Hz:
    /low_cmd Hermite C1 보간 (50 → 200 Hz)
    tau_motor = Kp(q_target − q) + Kd(qdot_target − qdot) + tau_ff
    data.ctrl[:] = clip(tau_motor, ±τ_max)
    mujoco.mj_step()

Joint order (MuJoCo qpos[7:] / qvel[6:] / ctrl[:]):
    0: HL_hip   1: HL_thigh  2: HL_calf  3: HL_foot
    4: HR_hip   5: HR_thigh  6: HR_calf  7: HR_foot
"""
import os
import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState, Imu
from std_msgs.msg import Float64MultiArray
from nav_msgs.msg import Odometry
from builtin_interfaces.msg import Time as TimeMsg

import mujoco


# ── 상수 ─────────────────────────────────────────────────────────────────────
MJCF_PATH_DEFAULT = '/home/jsh/simulation/biped/biped_wrapper.mjcf'
SIM_DT_DEFAULT    = 0.002    # 500 Hz mj_step (mjcf timestep 과 일치)
CTRL_PERIOD       = 0.005    # 200 Hz PD control
CMD_PERIOD        = 0.02     # /low_cmd 수신 주기 가정 (50 Hz)
PUBLISH_HZ_LOWS   = 50
N_DOF             = 8
KP_DEFAULT        = 80.0
KD_DEFAULT        = 4.0
TAU_MAX           = 200.0    # mjcf default motor ctrlrange ±200 (max torque 168Nm 보다 여유)

# Q_HOME standing pose (forward kinematics 로 검증, base_z=0.50 에서 발 끝 z≈0)
# leg order: HL_hip, HL_thigh, HL_calf, HL_foot, HR_hip, HR_thigh, HR_calf, HR_foot
# 좌우 axis 부호 반전: HL_thigh axis=(0,-1,0), HR_thigh=(0,1,0) → 같은 visual: sign 반대
#                    HL_foot  axis=(0,-1,0), HR_foot =(0,1,0) → 같은 visual: sign 반대
#                    HL_calf, HR_calf 둘 다 (0,-1,0) → 같은 sign
Q_HOME_RAD = [0.0] * 8   # URDF zero pose = robot standing (Hip Pitch -20°, Knee 130°, Ankle 130°)
                         # axis 통일 (HL/HR thigh/calf/foot 모두 (0,+1,0)) → 좌우 같은 sign
BASE_Z_HOME = 0.532      # 발 끝이 floor 와 정확히 접촉 (URDF zero pose)


# ── Hermite C1 보간 ──────────────────────────────────────────────────────────
def _hermite_pos(s, T, q0, q1, m0, m1):
    h00 =  2*s**3 - 3*s**2 + 1
    h10 =      s**3 - 2*s**2 + s
    h01 = -2*s**3 + 3*s**2
    h11 =      s**3 -   s**2
    return [h00*q0[i] + h10*T*m0[i] + h01*q1[i] + h11*T*m1[i]
            for i in range(len(q0))]


def _hermite_vel(s, T, q0, q1, m0, m1):
    h00d =  6*s**2 - 6*s
    h10d =  3*s**2 - 4*s + 1
    h01d = -6*s**2 + 6*s
    h11d =  3*s**2 - 2*s
    return [(h00d*q0[i] + h10d*T*m0[i] + h01d*q1[i] + h11d*T*m1[i]) / T
            for i in range(len(q0))]


class BipedMujocoNode(Node):
    """Biped MuJoCo simulator node."""

    def __init__(self):
        super().__init__('biped_mujoco_node')

        self.declare_parameter('mjcf_path', MJCF_PATH_DEFAULT)
        self.declare_parameter('sim_dt',    SIM_DT_DEFAULT)
        self.declare_parameter('use_viewer', False)
        self.declare_parameter('kp_default', KP_DEFAULT)
        self.declare_parameter('kd_default', KD_DEFAULT)

        mjcf_path        = self.get_parameter('mjcf_path').value
        self._sim_dt     = self.get_parameter('sim_dt').value
        self._use_viewer = self.get_parameter('use_viewer').value
        kp_init          = self.get_parameter('kp_default').value
        kd_init          = self.get_parameter('kd_default').value

        if not os.path.exists(mjcf_path):
            raise RuntimeError(f"MJCF not found: {mjcf_path}")
        self._model = mujoco.MjModel.from_xml_path(mjcf_path)
        self._data  = mujoco.MjData(self._model)
        self._model.opt.timestep = self._sim_dt

        if self._model.nu != N_DOF:
            self.get_logger().warn(
                f"mjcf nu ({self._model.nu}) != expected {N_DOF}"
            )

        self._joint_names = []
        for jid in range(1, self._model.njnt):   # skip freejoint
            n = mujoco.mj_id2name(self._model, mujoco.mjtObj.mjOBJ_JOINT, jid)
            if n is not None:
                self._joint_names.append(n)
        self.get_logger().info(
            f"MJCF loaded: nu={self._model.nu}, joints={self._joint_names}"
        )

        # 초기 자세
        self._data.qpos[0:3] = [0.0, 0.0, BASE_Z_HOME]
        self._data.qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
        self._data.qpos[7:]  = Q_HOME_RAD
        mujoco.mj_forward(self._model, self._data)

        # Hermite state
        self._lock = threading.Lock()
        self._interp_prev   = list(Q_HOME_RAD)
        self._interp_target = list(Q_HOME_RAD)
        self._interp_dq0    = [0.0] * N_DOF
        self._interp_dq1    = [0.0] * N_DOF
        self._interp_time   = time.monotonic()
        self._cmd_tau = [0.0] * N_DOF
        self._cmd_kp  = [kp_init] * N_DOF
        self._cmd_kd  = [kd_init] * N_DOF

        # ROS2 pub/sub
        self._sub_cmd = self.create_subscription(
            JointState, '/low_cmd', self._on_low_cmd, 10
        )
        self._sub_gains = self.create_subscription(
            Float64MultiArray, '/rl_gains', self._on_rl_gains, 10
        )
        self._pub_joint_states = self.create_publisher(JointState, '/joint_states', 10)
        self._pub_low_state    = self.create_publisher(JointState, '/low_state',    10)
        self._pub_imu          = self.create_publisher(Imu,        '/imu',          10)
        # /base_state: sim ground-truth base pose/twist (r4.1 EKF 이전 대체)
        self._pub_base_state   = self.create_publisher(Odometry,   '/base_state',   10)

        # Timers
        self._ctrl_timer = self.create_timer(CTRL_PERIOD, self._control_loop)
        self._pub_timer  = self.create_timer(1.0 / PUBLISH_HZ_LOWS, self._publish_states)

        # Viewer (옵션)
        self._viewer = None
        if self._use_viewer:
            try:
                from mujoco import viewer as _mj_viewer
                self._viewer = _mj_viewer.launch_passive(self._model, self._data)
                self.get_logger().info("MuJoCo viewer launched")
            except Exception as e:
                self.get_logger().warn(f"viewer launch failed (headless): {e}")

        self.get_logger().info(
            f"BipedMujocoNode ready | sim_dt={self._sim_dt} | "
            f"viewer={self._use_viewer} | Kp={kp_init} Kd={kd_init}"
        )

    def _on_low_cmd(self, msg: JointState):
        if len(msg.position) < N_DOF:
            self.get_logger().warn(
                f"/low_cmd: position len {len(msg.position)} < {N_DOF}"
            )
            return
        q     = list(msg.position[:N_DOF])
        dq    = list(msg.velocity[:N_DOF]) if len(msg.velocity) >= N_DOF else [0.0]*N_DOF
        tauff = list(msg.effort[:N_DOF])   if len(msg.effort)   >= N_DOF else [0.0]*N_DOF

        now = time.monotonic()
        with self._lock:
            elapsed = now - self._interp_time
            s = min(elapsed / CMD_PERIOD, 1.0)
            cur_pos = _hermite_pos(s, CMD_PERIOD,
                                    self._interp_prev, self._interp_target,
                                    self._interp_dq0,  self._interp_dq1)
            cur_vel = _hermite_vel(s, CMD_PERIOD,
                                    self._interp_prev, self._interp_target,
                                    self._interp_dq0,  self._interp_dq1)
            new_dq1 = [(q[i] - self._interp_target[i]) / CMD_PERIOD
                       for i in range(N_DOF)]
            self._interp_prev   = cur_pos
            self._interp_dq0    = cur_vel
            self._interp_target = q
            self._interp_dq1    = new_dq1
            self._interp_time   = now
            self._cmd_tau = tauff

    def _on_rl_gains(self, msg: Float64MultiArray):
        if len(msg.data) < N_DOF * 2:
            return
        with self._lock:
            self._cmd_kp = list(msg.data[:N_DOF])
            self._cmd_kd = list(msg.data[N_DOF:N_DOF*2])

    def _control_loop(self):
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._interp_time
            s = min(elapsed / CMD_PERIOD, 1.0)
            q_target  = _hermite_pos(s, CMD_PERIOD,
                                       self._interp_prev, self._interp_target,
                                       self._interp_dq0,  self._interp_dq1)
            qd_target = _hermite_vel(s, CMD_PERIOD,
                                       self._interp_prev, self._interp_target,
                                       self._interp_dq0,  self._interp_dq1)
            kp  = list(self._cmd_kp)
            kd  = list(self._cmd_kd)
            tff = list(self._cmd_tau)

        q_meas  = self._data.qpos[7:7+N_DOF].copy()
        qd_meas = self._data.qvel[6:6+N_DOF].copy()

        tau_motor = [
            kp[i] * (q_target[i] - q_meas[i])
            + kd[i] * (qd_target[i] - qd_meas[i])
            + tff[i]
            for i in range(N_DOF)
        ]
        tau_motor = [max(-TAU_MAX, min(TAU_MAX, t)) for t in tau_motor]
        self._data.ctrl[:N_DOF] = tau_motor

        # CTRL_PERIOD (5ms) 동안 mj_step 여러 번 (sim_dt=2ms 면 2~3 step)
        n_sub = max(1, int(round(CTRL_PERIOD / self._sim_dt)))
        for _ in range(n_sub):
            mujoco.mj_step(self._model, self._data)

        if self._viewer is not None:
            try:
                self._viewer.sync()
            except Exception:
                pass

    def _publish_states(self):
        ns = time.time_ns()
        stamp = TimeMsg(sec=ns // 10**9, nanosec=ns % 10**9)

        q  = self._data.qpos[7:7+N_DOF]
        dq = self._data.qvel[6:6+N_DOF]

        js = JointState()
        js.header.stamp = stamp
        js.name = list(self._joint_names)
        js.position = q.tolist()
        js.velocity = dq.tolist()
        js.effort   = self._data.ctrl[:N_DOF].tolist()

        self._pub_joint_states.publish(js)
        self._pub_low_state.publish(js)

        imu = Imu()
        imu.header.stamp = stamp
        imu.header.frame_id = 'base_link'
        q_b = self._data.qpos[3:7]
        imu.orientation.w = float(q_b[0])
        imu.orientation.x = float(q_b[1])
        imu.orientation.y = float(q_b[2])
        imu.orientation.z = float(q_b[3])
        w_b = self._data.qvel[3:6]
        imu.angular_velocity.x = float(w_b[0])
        imu.angular_velocity.y = float(w_b[1])
        imu.angular_velocity.z = float(w_b[2])
        a_b = self._data.qacc[0:3] if self._data.qacc is not None else np.zeros(3)
        imu.linear_acceleration.x = float(a_b[0])
        imu.linear_acceleration.y = float(a_b[1])
        imu.linear_acceleration.z = float(a_b[2])
        # base z (extra: position 의 첫 3-vec 를 covariance 자리에 임시 stuff 하지 않음)
        # 대신 ROS 표준 Imu 만 사용. base_z 는 /low_state position[-1] 등 다른 방식 추후.
        self._pub_imu.publish(imu)

        # /base_state: sim 의 ground-truth base pose/twist (controller 입력)
        od = Odometry()
        od.header.stamp = stamp
        od.header.frame_id = 'world'
        od.child_frame_id  = 'base_link'
        bp = self._data.qpos[0:3]
        bq = self._data.qpos[3:7]    # (w,x,y,z)
        bv = self._data.qvel[0:3]
        bw = self._data.qvel[3:6]
        od.pose.pose.position.x = float(bp[0])
        od.pose.pose.position.y = float(bp[1])
        od.pose.pose.position.z = float(bp[2])
        od.pose.pose.orientation.w = float(bq[0])
        od.pose.pose.orientation.x = float(bq[1])
        od.pose.pose.orientation.y = float(bq[2])
        od.pose.pose.orientation.z = float(bq[3])
        od.twist.twist.linear.x  = float(bv[0])
        od.twist.twist.linear.y  = float(bv[1])
        od.twist.twist.linear.z  = float(bv[2])
        od.twist.twist.angular.x = float(bw[0])
        od.twist.twist.angular.y = float(bw[1])
        od.twist.twist.angular.z = float(bw[2])
        self._pub_base_state.publish(od)

    def destroy_node(self):
        if self._viewer is not None:
            try:
                self._viewer.close()
            except Exception:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BipedMujocoNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
