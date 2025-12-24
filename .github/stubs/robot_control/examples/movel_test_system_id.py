#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
MoveL Test with System ID
=========================

This test demonstrates how to execute linear (MoveL) motions for multiple robot arms (with different system IDs) using the Motorcortex Robot Control API. It covers engaging each robot, building and sending linear motion programs, handling start position logic, and monitoring execution for each system.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Runs the MoveL test for two robot arms (system IDs 1 and 2).
3. For each robot:
   - Engages the robot and resets its state.
   - Defines Cartesian waypoints for MoveL motions.
   - Builds and sends point-to-point and waypoint linear motion programs.
   - Handles cases where the robot is not at the start position.
   - Monitors and prints the robot state during execution.
   - Stops the robot after completion.
4. Closes the connection after all tests are done.

Usage:
------
Run this file to see an example of executing linear motions for multiple robot arms using system IDs. Adjust waypoints, system IDs, and connection parameters as needed for your setup.
"""

import motorcortex
import math
import time
from robot_control.motion_program import MotionProgram, Waypoint
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates


def run(req, motorcortex_types, system_id):
    # Step 1: Create RobotCommand for the specified system ID
    robot = RobotCommand(req, motorcortex_types, system_id)

    # Step 2: Engage the robot
    if robot.engage():
        print('Robot is at Engage')
    else:
        raise Exception('Failed to set robot to Engage')

    # Step 3: Stop and reset the robot
    robot.stop()
    robot.reset()

    # Step 4: Define Cartesian waypoints for MoveL motions
    cart_pos_1 = Waypoint([0.4, 0, 1.295, 0, math.pi, 0])
    cart_pos_2 = Waypoint([0.3, 0, 1.295, 0, math.pi, 0])
    cart_pos_3 = Waypoint([0.3, 0.1, 1.295, 0, math.pi, 0])

    # Step 5: Build point-to-point linear motion program
    motion_pr_1 = MotionProgram(req, motorcortex_types, True)
    motion_pr_1.addMoveL([cart_pos_1], 0.5, 0.5)
    motion_pr_1.addMoveL([cart_pos_2], 0.5, 0.5)
    motion_pr_1.addMoveL([cart_pos_3], 0.5, 0.5)

    # Step 6: Build waypoint linear motion program
    motion_pr_2 = MotionProgram(req, motorcortex_types, True)
    motion_pr_2.addMoveL([cart_pos_1, cart_pos_2, cart_pos_3], 0.1, 0.1)

    # Step 7: Send and execute point-to-point motion program
    print('Start to play: {}'.format(robot.getState()))
    motion_pr_1.send("test1", system_id).get()
    if robot.play() is InterpreterStates.MOTION_NOT_ALLOWED_S.value:
        print('Robot is not at a start position, moving to the start')
        if robot.moveToStart(10):
            print('Robot is at the start position')
        else:
            raise Exception('Failed to move to the start position')

        robot.play()

    # Step 8: Monitor execution of point-to-point motion program
    while robot.getState() is InterpreterStates.PROGRAM_RUN_S.value:
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(robot.getState()))

    # Step 9: Send and execute second point-to-point motion program
    print('Continue to play: {}'.format(robot.getState()))
    motion_pr_1.send("test2", system_id).get()
    while robot.getState() is InterpreterStates.PROGRAM_IS_DONE.value:
        time.sleep(0.1)
        print('Waiting for the program to start, robot state: {}'.format(robot.getState()))
    while robot.getState() is InterpreterStates.PROGRAM_RUN_S.value:
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(robot.getState()))

    # Step 10: Send and execute waypoint linear motion program
    print('Continue to play: {}'.format(robot.getState()))
    motion_pr_2.send("test3", system_id).get()
    while robot.getState() is InterpreterStates.PROGRAM_IS_DONE.value:
        time.sleep(0.1)
        print('Waiting for the program to start, robot state: {}'.format(robot.getState()))
    while robot.getState() is InterpreterStates.PROGRAM_RUN_S.value:
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(robot.getState()))

    # Step 11: Stop the robot after completion
    robot.stop()
    # robot.reset()

    print('Done!')


def main():
    # Step 1: Create empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Step 2: Load protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Step 3: Open request connection to Motorcortex server
    req, sub = motorcortex.connect("wss://localhost:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")

    # Step 4: Run MoveL test for system IDs 1 and 2
    run(req, motorcortex_types, 1)
    run(req, motorcortex_types, 2)

    # Step 5: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
