"""standing_test.launch.py — v14.5.9-b standing 검증

실행:
    ros2 launch gait_sim_mujoco standing_test.launch.py
    ros2 launch gait_sim_mujoco standing_test.launch.py use_viewer:=true

Topics:
    /low_cmd  ← standing_publisher (50Hz Q_HOME)
    /low_state, /joint_states, /imu ← mujoco_node

기대 결과: base_z ≈ 0.465 m 5초 유지, joint q ≈ Q_HOME ± 0.05 rad
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_viewer = LaunchConfiguration('use_viewer')

    return LaunchDescription([
        DeclareLaunchArgument('use_viewer', default_value='false',
                              description='Launch MuJoCo 3D viewer'),

        Node(package='gait_sim_mujoco', executable='mujoco_node',
             name='mujoco_sim_node', output='screen',
             parameters=[{
                 'use_viewer': use_viewer,
                 'kp_default': 500.0,   # MuJoCo direct-drive 라 motorcortex 의 Kp 보다 큼
                 'kd_default': 20.0,
             }]),

        Node(package='gait_sim_mujoco', executable='standing_publisher',
             name='standing_publisher', output='screen'),
    ])
