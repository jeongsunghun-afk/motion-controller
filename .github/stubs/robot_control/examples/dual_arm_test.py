#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
Dual Arm Test
============

This test demonstrates how to coordinate and control two robot arms simultaneously using the MultiRobotCommand and MotionProgram classes from the motorcortex-robot-control-python API.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a MultiRobotCommand instance for two robot arms (system IDs 1 and 2).
3. Engages both robots and resets their state.
4. Defines Cartesian waypoints for both arms.
5. Creates and sends two types of motion programs:
   - Point-to-point linear moves (addMoveL)
   - Circular moves (addMoveC)
6. Sends the motion programs to both robots and synchronizes their execution.
7. Monitors and prints the state of both robots during execution.
8. Closes the connection after completion.

Usage:
------
Run this file to see an example of dual-arm coordination, including engaging, moving, and synchronizing two robots. Adjust waypoints and motion parameters as needed for your setup.
"""

import motorcortex
import math
import time
from robot_control.motion_program import MotionProgram, Waypoint, sendProgramList
from robot_control.multirobot_command import MultiRobotCommand, isEqual
from robot_control.system_defs import InterpreterStates


def main():
    # Step 1: Create empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Step 2: Load protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Step 3: Open request connection to Motorcortex server
    req, sub = motorcortex.connect("wss://localhost:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")

    # Step 4: Create MultiRobotCommand for two robot arms (system IDs 1 and 2)
    dual_arm = MultiRobotCommand(req, motorcortex_types, [1, 2])

    # Step 5: Engage both robots
    if dual_arm.engage():
        print('Robot is at Engage')
    else:
        raise Exception('Failed to set robot to Engage')

    # Step 6: Stop and reset both robots
    dual_arm.stop()
    dual_arm.reset()

    # Step 7: Define Cartesian waypoints for both arms
    cart_pos_1 = Waypoint([0.4, 0, 1.4, 0, math.pi, 0])
    cart_pos_2 = Waypoint([0.3, 0, 1.4, 0, math.pi, 0])
    cart_pos_3 = Waypoint([0.3, 0.1, 1.4, 0, math.pi, 0])

    # Step 8: Create point-to-point linear motion program for both arms
    motion_pr_1 = MotionProgram(req, motorcortex_types, True)
    motion_pr_1.addMoveL([cart_pos_1], 0.5, 0.5)
    motion_pr_1.addMoveL([cart_pos_2], 0.5, 0.5)
    motion_pr_1.addMoveL([cart_pos_3], 0.5, 0.5)
    motion_pr_1.addMoveL([cart_pos_1], 0.5, 0.5)

    # Step 9: Create circular motion program for both arms
    motion_pr_2 = MotionProgram(req, motorcortex_types, True)
    motion_pr_2.addMoveC([cart_pos_1, cart_pos_2, cart_pos_3], 10, 0.1, 10)

    # Step 10: Send first motion program to both robots
    print('Start to play: {}'.format(dual_arm.getState()))
    sendProgramList(req, motorcortex_types, [motion_pr_1, motion_pr_1], [1, 2]).get()

    # Step 11: Move both robots to start position
    dual_arm.moveToStart(10)

    # Step 12: Play synchronized motion programs
    dual_arm.play()
    # Wait until both robots are running the program
    while not isEqual(dual_arm.getState(), InterpreterStates.PROGRAM_RUN_S.value):
        time.sleep(0.1)
        print('Waiting for the program to start, robot state: {}'.format(dual_arm.getState()))
    # Wait until both robots have finished the program
    while not isEqual(dual_arm.getState(), InterpreterStates.PROGRAM_IS_DONE.value):
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(dual_arm.getState()))

    # Step 13: Send second (circular) motion program to both robots
    print('Start to play: {}'.format(dual_arm.getState()))
    sendProgramList(req, motorcortex_types, [motion_pr_2, motion_pr_2], [1, 2]).get()
    # Wait until both robots are running the program
    while not isEqual(dual_arm.getState(), InterpreterStates.PROGRAM_RUN_S.value):
        time.sleep(0.1)
        print('Waiting for the program to start, robot state: {}'.format(dual_arm.getState()))
    # Wait until both robots have finished the program
    while not isEqual(dual_arm.getState(), InterpreterStates.PROGRAM_IS_DONE.value):
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(dual_arm.getState()))

    # Step 14: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
