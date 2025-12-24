#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
MoveC Test
==========

This test demonstrates how to execute a circular (MoveC) motion with a robot arm using the Motorcortex Robot Control API. It covers engaging the robot, building a circular motion program, handling start position logic, and monitoring execution.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a RobotCommand instance for a single robot arm.
3. Engages the robot and resets its state.
4. Defines Cartesian waypoints for the circular move.
5. Builds and sends a circular motion program (MoveC).
6. Handles cases where the robot is not at the start position.
7. Monitors and prints the robot state during execution.
8. Closes the connection after completion.

Usage:
------
Run this file to see an example of executing a circular motion with a robot arm. Adjust waypoints and connection parameters as needed for your setup.
"""

import motorcortex
import math
import time
from robot_control.motion_program import Waypoint, MotionProgram
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates


def main():
    # Step 1: Create empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Step 2: Load protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Step 3: Open request connection to Motorcortex server
    req, sub = motorcortex.connect("wss://localhost:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=5000,
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

    # Step 7: Define Cartesian waypoints for the circular move
    cart_pos_1 = Waypoint([0.4, 0, 0.295, 0, math.pi, 0])
    cart_pos_2 = Waypoint([0.3, 0, 0.295, 0, math.pi, 0])
    cart_pos_3 = Waypoint([0.3, 0.1, 0.295, 0, math.pi, 0])

    # Step 8: Build circular motion program (MoveC)
    motion_pr_2 = MotionProgram(req, motorcortex_types)
    motion_pr_2.addMoveC([cart_pos_1, cart_pos_2, cart_pos_3], 3 * math.pi, 0.1, 0.1)

    # Step 9: Send the motion program and start execution
    print('Start to play: {}'.format(robot.getState()))
    motion_pr_2.send("test1").get()
    if robot.play() is InterpreterStates.MOTION_NOT_ALLOWED_S.value:
        print('Robot is not at a start position, moving to the start')
        if robot.moveToStart(10):
            print('Robot is at the start position')
        else:
            raise Exception('Failed to move to the start position')

        robot.play()

    # Step 10: Wait for the program to start and monitor execution
    while robot.getState() is InterpreterStates.PROGRAM_IS_DONE.value:
        time.sleep(0.1)
        print('Waiting for the program to start, robot state: {}'.format(robot.getState()))
    while robot.getState() is InterpreterStates.PROGRAM_RUN_S.value:
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(robot.getState()))

    print('Done!')

    # Step 11: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
