from setuptools import setup
import os
from glob import glob

package_name = 'biped_sim'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name, package_name + '.controllers'],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jsh',
    maintainer_email='jeong.sunghun@rgarobot.com',
    description='biped (HL/HR 2-leg) MuJoCo ROS2 sim node',
    license='BSD',
    entry_points={
        'console_scripts': [
            'mujoco_node        = biped_sim.mujoco_node:main',
            'standing_publisher = biped_sim.standing_publisher:main',
            'controller_node    = biped_sim.controller_node:main',
        ],
    },
)
