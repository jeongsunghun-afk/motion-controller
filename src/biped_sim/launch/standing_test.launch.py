"""standing_test.launch.py — biped_sim standing 검증.

Usage:
    ros2 launch biped_sim standing_test.launch.py
    ros2 launch biped_sim standing_test.launch.py use_viewer:=true
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

        Node(package='biped_sim', executable='mujoco_node',
             name='biped_mujoco_node', output='screen',
             parameters=[{
                 'use_viewer': use_viewer,
                 'kp_default': 200.0,
                 'kd_default': 10.0,
             }]),

        Node(package='biped_sim', executable='standing_publisher',
             name='standing_publisher', output='screen'),
    ])
