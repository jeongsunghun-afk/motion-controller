"""standing_publisher.py — manual /low_cmd publisher for v14.5.9-b standing test.

50 Hz 로 /low_cmd 에 Q_HOME 자세를 publish.
mujoco_node 가 Hermite 50→200Hz 보간 + PD 로 standing 유지 가능한지 검증.

usage:
    ros2 run gait_sim_mujoco standing_publisher
"""
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

# gait_sim model.py 와 일치 (leg-major: FR / FL / HR / HL)
_Q_HOME_FRONT_DEG = [0.0, 133.2973, 46.7027, 30.6583, 59.3417]
_Q_HOME_HIND_DEG  = [0.0, -150.0,   -90.0,   90.0,    60.0]
Q_HOME_RAD = [math.radians(v) for v in
              _Q_HOME_FRONT_DEG + _Q_HOME_FRONT_DEG +
              _Q_HOME_HIND_DEG  + _Q_HOME_HIND_DEG]
N_DOF = 20
HZ    = 50


class StandingPublisher(Node):
    def __init__(self):
        super().__init__('standing_publisher')
        self.pub = self.create_publisher(JointState, '/low_cmd', 10)
        self.timer = self.create_timer(1.0 / HZ, self._tick)
        self.get_logger().info(f"StandingPublisher start: 50Hz Q_HOME → /low_cmd")
        self._n = 0

    def _tick(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.position = list(Q_HOME_RAD)
        msg.velocity = [0.0] * N_DOF
        msg.effort   = [0.0] * N_DOF
        self.pub.publish(msg)
        self._n += 1
        if self._n % HZ == 0:
            self.get_logger().info(f"published {self._n} cmds ({self._n//HZ}s)")


def main(args=None):
    rclpy.init(args=args)
    node = StandingPublisher()
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
