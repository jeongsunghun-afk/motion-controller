#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
States Test
===========

This test demonstrates how to transition a robot arm through various states using the Motorcortex Robot Control API. It covers error acknowledgement, engaging, disengaging, and turning the robot off, with state checks and printed feedback for each transition.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a RobotCommand instance for a single robot arm.
3. Acknowledges any errors or warnings.
4. Transitions the robot through Engage, Disengage, and Off states, printing the result of each transition.
5. Repeats Engage and Off transitions to demonstrate state changes.
6. Closes the connection after completion.

Usage:
------
Run this file to see an example of state transitions for a single robot arm. Adjust connection parameters and states as needed for your setup.
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
    req, sub = motorcortex.connect("wss://192.168.2.101:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")
    print(type(req))

    # Step 4: Create RobotCommand for a single robot arm
    robot = RobotCommand(req, motorcortex_types)

    # Step 5: Acknowledge any errors or warnings
    if robot.acknowledge():
        print('Robot is Errors are acknowledged')
    else:
        print('Failed to acknowledge errors')

    # Step 6: Transition to Engage state
    if robot.engage():
        print('Robot is at Engage')
    else:
        print('Failed to set robot to Engage')

    time.sleep(1)

    # Step 7: Transition to Disengage state
    if robot.disengage():
        print('Robot is at Disengage')
    else:
        print('Failed to set robot to disengage')

    time.sleep(1)

    # Step 8: Transition to Off state
    if robot.off():
        print('Robot is Off')
    else:
        print('Failed to set robot to Off')

    time.sleep(1)

    # Step 9: Transition to Engage state again
    if robot.engage():
        print('Robot is at Engage')
    else:
        print('Failed to set robot to Engage')

    time.sleep(1)

    # Step 10: Transition to Off state again
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
