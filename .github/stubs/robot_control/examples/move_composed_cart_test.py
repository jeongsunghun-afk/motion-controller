#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

import motorcortex
import math
import time
from robot_control.motion_program import MotionProgram, Waypoint
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates


def main():
    # Creating empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Loading protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Open request connection
    req, sub = motorcortex.connect("wss://localhost:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")

    robot = RobotCommand(req, motorcortex_types)

    if robot.engage():
        print('Robot is at Engage')
    else:
        raise Exception('Failed to set robot to Engage')

    robot.stop()
    robot.reset()

    cart_pos_1 = Waypoint([0.4, 0.00, 0.35, 0, math.pi, 0])
    cart_pos_2 = Waypoint([0.4, -0.15, 0.35, 0, math.pi, 0])
    cart_pos_2c = Waypoint([0.4, -0.200, 0.3, 0, math.pi, 0])
    cart_pos_3 = Waypoint([0.4, -0.15, 0.25, 0, math.pi, 0])
    cart_pos_4 = Waypoint([0.4, 0.00, 0.25, 0, math.pi, 0])
    cart_pos_4c = Waypoint([0.4, 0.05, 0.30, 0, math.pi, 0])

    cart_pos_5 = Waypoint([0.4, -0.10, 0.30, 0, math.pi, 0])
    cart_pos_6 = Waypoint([0.4, -0.05, 0.35, 0, math.pi, 0])
    cart_pos_7 = Waypoint([0.4, 0.00, 0.30, 0, math.pi, 0])

    cart_pos_8 = Waypoint([0.4, -0.05, 0.25, 0, math.pi, 0])
    cart_pos_9 = Waypoint([0.4, -0.15, 0.35, 0, math.pi, 0])

    # point to point move
    motion_pr_1 = MotionProgram(req, motorcortex_types)
    movel1 = motion_pr_1.createMoveL([cart_pos_1, cart_pos_2], 0.1, 0.5)
    movec1 = motion_pr_1.createMoveC([cart_pos_2, cart_pos_2c, cart_pos_3], 0, 0.1, 0.1, 0.1)
    movel2 = motion_pr_1.createMoveL([cart_pos_3, cart_pos_4], 0.1, 0.5)
    movec2 = motion_pr_1.createMoveC([cart_pos_4, cart_pos_4c, cart_pos_1], 0, 0.1, 0.1)

    movec3 = motion_pr_1.createMoveC([cart_pos_2c, cart_pos_3, cart_pos_5], 0, 0.1, 0.1)
    movec4 = motion_pr_1.createMoveC([cart_pos_5, cart_pos_6, cart_pos_7], 0, 0.1, 0.1)
    movec5 = motion_pr_1.createMoveC([cart_pos_7, cart_pos_8, cart_pos_5], 0, 0.1, 0.1)
    movec6 = motion_pr_1.createMoveC([cart_pos_5, cart_pos_9, cart_pos_2c], 0, 0.1, 0.1)

    motion_pr_1.addComposedCartMove([movel1, movec1, movel2, movec2])
    motion_pr_1.addMoveL([cart_pos_2c])
    motion_pr_1.addComposedCartMove([movec3, movec4, movec5, movec6])

    print('Start to play: {}'.format(robot.getState()))
    motion_pr_1.send("test1").get()
    if robot.play() is InterpreterStates.MOTION_NOT_ALLOWED_S.value:
        print('Robot is not at a start position, moving to the start')
        if robot.moveToStart(10):
            print('Robot is at the start position')
        else:
            raise Exception('Failed to move to the start position')

        robot.play()

    while robot.getState() is InterpreterStates.PROGRAM_RUN_S.value:
        time.sleep(0.1)
        print('Playing, robot state: {}'.format(robot.getState()))

    print('Done!')

    req.close()
    sub.close()


if __name__ == '__main__':
    main()
