#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
Modes Test
==========

This test demonstrates how to switch a robot between different control modes using the Motorcortex Robot Control API. It covers engaging the robot, switching between manual Cartesian and joint modes, and turning the robot off.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a RobotCommand instance for a single robot arm.
3. Resets the robot state.
4. Engages the robot.
5. Switches between manual Cartesian and joint modes, printing the result of each transition.
6. Turns the robot off and closes the connection.

Usage:
------
Run this file to see an example of mode switching for a single robot arm. Adjust connection parameters and modes as needed for your setup.
"""

import motorcortex
from robot_control.robot_command import RobotCommand
import time


def main():
    # Step 1: Create empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Step 2: Load protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Step 3: Open request connection to Motorcortex server
    req, sub = motorcortex.connect("wss://192.168.2.100:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")

    # Step 4: Create RobotCommand for a single robot arm
    robot = RobotCommand(req, motorcortex_types)

    # Step 5: Reset the robot state
    robot.reset()

    # Step 6: Engage the robot
    if robot.engage():
        print('Robot is at Engage')
    else:
        print('Failed to set robot to Engage')

    time.sleep(1)

    # Step 7: Switch to Manual Cartesian Mode
    if robot.manualCartMode():
        print('Robot is in Manual Cartesian Mode')
    else:
        print('Failed to set robot to Manual Cartesian Mode')

    time.sleep(1)

    # Step 8: Switch to Manual Joint Mode
    if robot.manualJointMode():
        print('Robot is in Manual Joint Mode')
    else:
        print('Failed to set robot to Manual Joint Mode')

    time.sleep(1)

    # Step 9: Switch back to Manual Cartesian Mode
    if robot.manualCartMode():
        print('Robot is in Manual Cartesian Mode')
    else:
        print('Failed to set robot to Manual Cartesian Mode')

    time.sleep(1)

    # Step 10: Turn the robot off
    if robot.off():
        print('Robot is Off')
    else:
        print('Failed to set robot to Off')

    time.sleep(1)

    # Step 11: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
