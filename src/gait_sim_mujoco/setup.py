from setuptools import setup
import os
from glob import glob

package_name = 'gait_sim_mujoco'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jsh',
    maintainer_email='TODO@email.com',
    description='gait_sim MuJoCo ROS2 sim node — unitree_mujoco 구조',
    license='BSD',
    entry_points={
        'console_scripts': [
            'mujoco_node         = gait_sim_mujoco.mujoco_node:main',
            'controller_node     = gait_sim_mujoco.controller_node:main',
            'standing_publisher  = gait_sim_mujoco.standing_publisher:main',
        ],
    },
)
