"""standing_publisher.py — 50 Hz /low_cmd Q_HOME publisher.

biped standing test 용. mujoco_node 가 Hermite+PD 로 Q_HOME 유지하는지 검증.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


Q_HOME_RAD = [0.0] * 8   # URDF zero pose = robot standing (좌우 같은 sign, axis 통일)
N_DOF = 8
HZ    = 50


class StandingPublisher(Node):
    def __init__(self):
        super().__init__('standing_publisher')
        self.pub = self.create_publisher(JointState, '/low_cmd', 10)
        self.timer = self.create_timer(1.0 / HZ, self._tick)
        self.get_logger().info("StandingPublisher start: 50Hz Q_HOME -> /low_cmd")
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
