"""wbic_standing.launch.py — biped WBIC standing test.

    mujoco_node    : sim (publishes /joint_states, /imu, /base_state, /low_state)
    controller_node: WBIC (subs above; publishes /low_cmd 의 effort 에 tau_ff)
    mujoco_node    : /low_cmd 받아서 tau_ff + small PD → motor

Usage:
    ros2 launch biped_sim wbic_standing.launch.py
    ros2 launch biped_sim wbic_standing.launch.py use_viewer:=true
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_viewer = LaunchConfiguration('use_viewer')

    return LaunchDescription([
        DeclareLaunchArgument('use_viewer', default_value='false'),

        Node(package='biped_sim', executable='mujoco_node',
             name='biped_mujoco_node', output='screen',
             parameters=[{
                 'use_viewer': use_viewer,
                 'kp_default': 20.0,    # 작은 PD (WBIC tau_ff 가 주력)
                 'kd_default': 1.0,
             }]),

        Node(package='biped_sim', executable='controller_node',
             name='biped_controller_node', output='screen'),
    ])
