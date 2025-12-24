#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
Move to Point Test
=================

This test demonstrates how to move a robot arm to specific joint positions using the Motorcortex Robot Control API. It covers engaging the robot, moving to several joint positions, and closing the connection.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a RobotCommand instance for a single robot arm.
3. Engages the robot and resets its state.
4. Moves the robot to a series of joint positions, printing the result of each move.
5. Closes the connection after completion.

Usage:
------
Run this file to see an example of moving a robot arm to specific joint positions. Adjust joint positions and connection parameters as needed for your setup.
"""

import motorcortex
import math
from robot_control.robot_command import RobotCommand


def main():
    # Step 1: Create empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Step 2: Load protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Step 3: Open request connection to Motorcortex server
    req, sub = motorcortex.connect("wss://localhost:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")

    # Step 4: Create RobotCommand for a single robot arm
    robot = RobotCommand(req, motorcortex_types)

    # Step 5: Engage the robot
    if robot.engage():
        print('Robot is at Engage')
    else:
        raise Exception('Failed to set robot to Engage')

    # Step 6: Stop and reset the robot
    robot.stop()
    robot.reset()

    # Step 7: Define joint positions to move to
    jpos_1 = [math.radians(0.0), math.radians(0.0), math.radians(90.0),
              math.radians(0.0), math.radians(90.0), math.radians(0.0)]
    jpos_2 = [math.radians(0.0), math.radians(0.0), math.radians(0.0),
              math.radians(0.0), math.radians(0.0), math.radians(0.0)]
    jpos_3 = [math.radians(15.0), math.radians(0.0), math.radians(0.0),
              math.radians(0.0), math.radians(0.0), math.radians(0.0)]
    jpos_4 = [math.radians(15.0), math.radians(0.0), math.radians(90.0),
              math.radians(0.0), math.radians(90.0), math.radians(0.0)]

    # Step 8: Move the robot to each joint position and print the result
    if robot.moveToPoint(jpos_1):
        print("Moved robot to jpos_1")
    else:
        print("Failed to move robot to jpos_1")

    if robot.moveToPoint(jpos_2):
        print("Moved robot to jpos_2")
    else:
        print("Failed to move robot to jpos_2")

    if robot.moveToPoint(jpos_3):
        print("Moved robot to jpos_3")
    else:
        print("Failed to move robot to jpos_3")

    if robot.moveToPoint(jpos_4):
        print("Moved robot to jpos_4")
    else:
        print("Failed to move robot to jpos_4")

    print('Done!')

    # Step 9: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
