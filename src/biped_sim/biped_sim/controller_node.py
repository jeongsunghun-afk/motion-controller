"""biped_sim.controller_node — WBIC standing controller (B1-d).

Subscribes:
    /joint_states  (sensor_msgs/JointState)  ← q, qdot (URDF angle, 8-dim)
    /imu           (sensor_msgs/Imu)         ← base orientation, omega
    /base_state    (nav_msgs/Odometry)       ← base pos/vel ground truth (sim 전용)

Publishes:
    /low_cmd       (sensor_msgs/JointState)  → q_target, qdot_target, tau_ff (8-dim)

내부 흐름 @ 100 Hz:
    BipedMjModel.set_state(base_pos, base_quat, q_legs, base_vel, base_omega, qdot_legs)
    → leg_dynamics + foot_jac + body_state
    → biped WBIC QP (28-dim)
    → tau_ff_total = tau_ff_input + Δτ  (per leg, 4×2 = 8)
    → /low_cmd publish: position=q_meas (PD 0 = tau_ff only), effort=tau_ff_total
"""
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState, Imu
from nav_msgs.msg import Odometry

from biped_sim.controllers.model import BipedMjModel
from biped_sim.controllers.wbic  import wbic_qp_full_biped


MJCF_PATH_DEFAULT = '/home/jsh/simulation/biped/biped_wrapper.mjcf'
CONTROL_HZ        = 100   # 100 Hz WBIC

# WBIC 비용 가중치
W_FB    = 1.0
W_DDQ   = 1e-1
W_TAU   = 1e-3
W_LAM   = 1e-4
LAMZ_MIN = 1.0    # N
MU      = 0.6


class BipedControllerNode(Node):
    def __init__(self):
        super().__init__('biped_controller_node')

        self.declare_parameter('mjcf_path', MJCF_PATH_DEFAULT)
        mjcf_path = self.get_parameter('mjcf_path').value

        self._mdl = BipedMjModel(mjcf_path)
        self.get_logger().info(
            f"BipedMjModel loaded: nq={self._mdl.nq}, nv={self._mdl.nv}, nu={self._mdl.nu}"
        )

        # State cache (모든 sub 가 set, control loop 가 read)
        self._lock = threading.Lock()
        self._q_legs    = np.zeros(8)
        self._qdot_legs = np.zeros(8)
        self._base_pos  = np.array([0., 0., 0.55])
        self._base_quat = np.array([1., 0., 0., 0.])
        self._base_vel  = np.zeros(3)
        self._base_om   = np.zeros(3)
        self._got_js    = False
        self._got_imu   = False
        self._got_base  = False

        # ROS2 pub/sub
        self.create_subscription(JointState, '/joint_states', self._on_js,   10)
        self.create_subscription(Imu,        '/imu',          self._on_imu,  10)
        self.create_subscription(Odometry,   '/base_state',   self._on_base, 10)
        self._pub_cmd = self.create_publisher(JointState, '/low_cmd', 10)

        # Control timer
        self.create_timer(1.0 / CONTROL_HZ, self._control_loop)

        self.get_logger().info(f"BipedControllerNode ready @ {CONTROL_HZ}Hz")

    # ── subs ──────────────────────────────────────────────────────────────
    def _on_js(self, msg: JointState):
        if len(msg.position) < 8:
            return
        with self._lock:
            self._q_legs    = np.array(msg.position[:8])
            if len(msg.velocity) >= 8:
                self._qdot_legs = np.array(msg.velocity[:8])
            self._got_js = True

    def _on_imu(self, msg: Imu):
        with self._lock:
            self._base_quat = np.array([msg.orientation.w, msg.orientation.x,
                                        msg.orientation.y, msg.orientation.z])
            self._base_om   = np.array([msg.angular_velocity.x,
                                        msg.angular_velocity.y,
                                        msg.angular_velocity.z])
            self._got_imu = True

    def _on_base(self, msg: Odometry):
        with self._lock:
            self._base_pos = np.array([msg.pose.pose.position.x,
                                       msg.pose.pose.position.y,
                                       msg.pose.pose.position.z])
            self._base_vel = np.array([msg.twist.twist.linear.x,
                                       msg.twist.twist.linear.y,
                                       msg.twist.twist.linear.z])
            self._got_base = True

    # ── control loop @ CONTROL_HZ ─────────────────────────────────────────
    def _control_loop(self):
        with self._lock:
            if not (self._got_js and self._got_imu and self._got_base):
                return
            q_legs    = self._q_legs.copy()
            qdot_legs = self._qdot_legs.copy()
            bp = self._base_pos.copy()
            bq = self._base_quat.copy()
            bv = self._base_vel.copy()
            bw = self._base_om.copy()

        # set BipedMjModel state → mj_forward
        self._mdl.set_state(bp, bq, q_legs, bv, bw, qdot_legs)

        # body info
        body = self._mdl.body_state()
        M_total = body['M_total']

        # per-leg dyn
        M_HL, h_HL = self._mdl.leg_dynamics('HL')
        M_HR, h_HR = self._mdl.leg_dynamics('HR')
        M_legs = [M_HL, M_HR]
        h_legs = [h_HL, h_HR]

        # foot Jacobian (3×4)
        J_HL = self._mdl.foot_jac_leg('HL')
        J_HR = self._mdl.foot_jac_leg('HR')
        J_legs = [J_HL, J_HR]

        # foot world pos
        foot_world_all = np.array([self._mdl.foot_world('HL'),
                                   self._mdl.foot_world('HR')])

        # 가정: standing — 양 발 stance, GRF 균등 분배 (z 만)
        contact_mask = [True, True]
        lam_des_all = np.array([[0., 0., M_total * 9.81 / 2],
                                [0., 0., M_total * 9.81 / 2]])

        # desired: 정지 유지 (ddq=0, v_dot=0, tau_ff=0)
        ddq_des_legs = [np.zeros(4), np.zeros(4)]
        tau_ff_legs  = [np.zeros(4), np.zeros(4)]
        v_dot_des_fb = np.zeros(6)

        # body inertia: 단순화 — base link diag inertia 사용
        I_body = np.diag(self._mdl.model.body_inertia[1])  # body[1] = base_link

        # WBIC solve
        result = wbic_qp_full_biped(
            M_legs, h_legs, ddq_des_legs, tau_ff_legs, lam_des_all,
            J_legs, contact_mask, foot_world_all, bp, v_dot_des_fb,
            M_total, I_body, bw,
            w_fb=W_FB, w_ddq=W_DDQ, w_tau=W_TAU, w_lam=W_LAM,
            lamz_min=LAMZ_MIN, mu=MU,
        )

        if result is None:
            self.get_logger().warn("WBIC QP failed")
            return

        # tau_total = tau_ff_input + Δτ  (per leg)
        tau_HL = tau_ff_legs[0] + result['d_tau_legs'][0]
        tau_HR = tau_ff_legs[1] + result['d_tau_legs'][1]
        tau_total = np.concatenate([tau_HL, tau_HR])

        # publish /low_cmd: q_target = q_meas (PD 0), effort = tau_ff
        cmd = JointState()
        cmd.header.stamp = self.get_clock().now().to_msg()
        cmd.position = q_legs.tolist()       # PD ref = current (0 error)
        cmd.velocity = qdot_legs.tolist()
        cmd.effort   = tau_total.tolist()
        self._pub_cmd.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = BipedControllerNode()
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
