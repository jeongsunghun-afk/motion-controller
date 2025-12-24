#!/usr/bin/python3
from time import sleep

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

import motorcortex
import math
import time
from robot_control.motion_program import MotionProgram
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates


def make_test_program(motion_pr_1, path):
    motion_pr_1.addSet(path, True)
    motion_pr_1.addWait(3)
    motion_pr_1.addSet(path, False)
    motion_pr_1.addWait(3)

    motion_pr_1.addSet(path, 1)
    motion_pr_1.addWait(3)
    motion_pr_1.addSet(path, 0)
    motion_pr_1.addWait(3)

    motion_pr_1.addSet(path, 2.4)
    motion_pr_1.addWait(3)
    motion_pr_1.addSet(path, 0.0)
    motion_pr_1.addWait(3)

    return motion_pr_1


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

    motion_pr_1 = make_test_program(MotionProgram(req, motorcortex_types), "root/UserParameters/moduleParamBool")
    motion_pr_1 = make_test_program(motion_pr_1, "root/UserParameters/moduleParamInt")
    motion_pr_1 = make_test_program(motion_pr_1, "root/UserParameters/moduleParamDouble")

    print('Start to play: {}'.format(robot.getState()))
    motion_pr_1.send("test1").get()
    robot.play()

    sleep(60)

    print('Done!')

    req.close()
    sub.close()


if __name__ == '__main__':
    main()
