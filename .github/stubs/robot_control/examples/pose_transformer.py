#!/usr/bin/python3

#
#   Developer : Alexey Zakharov (alexey.zakharov@vectioneer.com)
#   All rights reserved. Copyright (c) 2020 VECTIONEER.
#

"""
Pose Transformer Test
====================

This test demonstrates how to use the PoseTransformer class from the Motorcortex Robot Control API to convert between joint and Cartesian coordinates for a robot arm. It covers forward and inverse kinematics, system ID usage, and validation of coordinate transformations.

Main Steps:
-----------
1. Connects to the Motorcortex server and initializes the parameter tree and protobuf types.
2. Creates a PoseTransformer instance for a robot arm.
3. Converts joint coordinates to Cartesian coordinates (forward kinematics).
4. Converts Cartesian coordinates back to joint coordinates (inverse kinematics).
5. Validates the transformation by comparing original and calculated joint coordinates.
6. Demonstrates transformations for different system IDs.
7. Closes the connection after completion.

Usage:
------
Run this file to see an example of using the PoseTransformer for kinematic transformations. Adjust joint and Cartesian coordinates as needed for your setup.
"""

import motorcortex
import math
from robot_control.motion_program import PoseTransformer


def is_close(n1, n2, abs_tol=1e-09):
    # Utility function to compare two lists of numbers with a given absolute tolerance
    if len(n1) != len(n2):
        return False
    for n1, n2 in zip(n1, n2):
        if not math.isclose(n1, n2, abs_tol=abs_tol):
            return False
    return True


def main():
    # Step 1: Create empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()

    # Step 2: Load protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()

    # Step 3: Open request connection to Motorcortex server
    req, sub = motorcortex.connect("wss://localhost:5568:5567", motorcortex_types, parameter_tree,
                                   certificate="mcx.cert.pem", timeout_ms=1000,
                                   login="", password="")

    # Step 4: Create PoseTransformer for a robot arm
    pose_transformer = PoseTransformer(req, motorcortex_types)

    # Step 5: Define reference joint coordinates
    ref_joint_coord = [0, 0, math.radians(90), 0, math.radians(90), 0]
    # Convert joint to Cartesian coordinates (forward kinematics)
    cart = pose_transformer.calcJointToCartPose(joint_coord_rad=ref_joint_coord)
    ref_cart_coord = cart.jointtocartlist[0].cartpose.coordinates
    print(f"system: {cart}")

    # Demonstrate transformation for system ID 1
    cart1 = pose_transformer.calcJointToCartPose(joint_coord_rad=ref_joint_coord, system_id=1)
    print(f"system1: {cart1}")

    # Demonstrate transformation for system ID 2
    cart2 = pose_transformer.calcJointToCartPose(joint_coord_rad=ref_joint_coord, system_id=2)
    print(f"system2: {cart2}")

    # Convert Cartesian back to joint coordinates (inverse kinematics)
    joint = pose_transformer.calcCartToJointPose(cart_coord=ref_cart_coord)
    print(f"system: {joint}")
    new_joint_coord = joint.carttojointlist[0].jointpose.coordinates
    # Validate transformation
    if is_close(new_joint_coord, ref_joint_coord):
        print("Reference joint values are equal to calculated values")
    else:
        print("Reference joint values are NOT equal to calculated values")

    # Demonstrate inverse kinematics for system ID 1
    joint1 = pose_transformer.calcCartToJointPose(cart_coord=[0.536, -0.23, 1.66, math.pi, 0, math.pi], system_id=1)
    print(f"system1: {joint1}")

    # Demonstrate inverse kinematics for system ID 2
    joint2 = pose_transformer.calcCartToJointPose(cart_coord=[0.536, 0.23, 1.66, math.pi, 0, math.pi], system_id=2)
    print(f"system2: {joint2}")

    # Step 6: Close the connection
    req.close()
    sub.close()


if __name__ == '__main__':
    main()
