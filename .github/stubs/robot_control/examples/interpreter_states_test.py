#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
Interpreter States Test
======================

This test demonstrates how to build, send, and execute a motion program for a single robot arm using the Motorcortex Robot Control API. It covers state transitions, program execution, error handling, and moving the robot to the start position if required.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a RobotCommand instance for a single robot arm.
3. Builds a sample motion program with joint waypoints.
4. Engages the robot and resets its state.
5. Sends the motion program to the robot.
6. Attempts to play the program, handling cases where the robot is not at the start position.
7. Waits for the program to finish.
8. Switches the robot off and closes the connection.

Usage:
------
Run this file to see an example of single-arm program execution, including state management and error handling. Adjust waypoints and motion parameters as needed for your setup.
"""

import motorcortex
from robot_control import to_radians
from robot_control.robot_command import RobotCommand
from robot_control.motion_program import MotionProgram, Waypoint
from robot_control.system_defs import InterpreterStates
import time


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

    # Step 5: Build example motion program with joint waypoints
    motion_program = MotionProgram(req, motorcortex_types)

    start_position_jnt = Waypoint(to_radians([0.0, 0.0, 90.0, 0.0, 90.0, 0.0]))
    jpos_1 = Waypoint(to_radians([15.0, 0.0, 90.0, 0.0, 90.0, 0.0]))
    jpos_2 = Waypoint(to_radians([30.0, 15.0, 90.0, 0.0, 90.0, 0.0]))
    jpos_3 = Waypoint(to_radians([-30.0, -15.0, 90.0, 15.0, 90.0, 15.0]))

    motion_program.addMoveJ([start_position_jnt], 0.5, 0.5)
    motion_program.addMoveJ([jpos_1, jpos_2], 1.0, 0.5)
    motion_program.addMoveJ([jpos_2, jpos_3], 0.5, 1.0)
    motion_program.addMoveJ([start_position_jnt], 1.0, 0.3)

    # Step 6: Engage the robot
    if robot.engage():
        print('Robot is at Engage')
    else:
        print('Failed to set robot to Engage')

    # Step 7: Reset the robot state
    robot.reset()

    # Step 8: Send the motion program to the robot
    program_sent = motion_program.send("example1").get()
    if program_sent.status == motorcortex.OK:
        print("Motion Program sent")
    else:
        raise RuntimeError("Failed to send Motion Program")

    # Step 9: Try to play the program
    play_state = robot.play()
    if play_state == InterpreterStates.PROGRAM_RUN_S.value:
        print("Playing program")
    elif play_state == InterpreterStates.MOTION_NOT_ALLOWED_S.value:
        print("Can not play program, Robot is not at start")
        print("Moving to start")
        # Move robot to start position if not allowed to play
        if robot.moveToStart(100):
            print("Move to start completed")
            if robot.play() == InterpreterStates.PROGRAM_RUN_S.value:
                print("Playing program")
            else:
                raise RuntimeError("Failed to play program, state: %s" % robot.getState())
        else:
            raise RuntimeError('Failed to move to start')
    else:
        raise RuntimeError("Failed to play program, state: %s" % robot.getState())

    # Step 10: Wait until the program is finished
    while robot.getState() != InterpreterStates.PROGRAM_IS_DONE.value:
        time.sleep(1)

    # Step 11: Switch off the robot
    if robot.off():
        print('Robot is Off')
    else:
        print('Failed to set robot to Off')

    # Step 12: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
