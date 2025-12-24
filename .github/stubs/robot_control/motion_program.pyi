import motorcortex
from _typeshed import Incomplete
from robot_control.system_defs import FrameTypes as FrameTypes
from typing import Any

def sendProgramList(req: motorcortex.Request, motorcortex_types: motorcortex.MessageTypes, motion_programs: list, systems_id: list[int]) -> motorcortex.ParameterTree:
    """Sends programs to the multiple systems

        Args:
            req(motorcortex.Request): reference to a Request instance
            motorcortex_types(motorcortex.MessageTypes): reference to a MessageTypes instance
            motion_programs(list(MotionProgram)): a list of motion programs
            systems_id(list(int)): a list of systems id
    """

class Waypoint:
    """Class represents a waypoint of the motion path

        Args:
            pose(list(double)): pose in Cartesian or joint space
            smoothing_factor(double): waypoint smoothing factor in the range [0..1]
            next_segment_velocity_factor(double) segment velocity factor in the range [0..1]

    """
    pose: Incomplete
    smoothing_factor: Incomplete
    next_segment_velocity_factor: Incomplete
    def __init__(self, pose: list[float], smoothing_factor: float = 0.1, next_segment_velocity_factor: float = 1.0) -> None: ...

class PoseTransformer:
    """Convert Cartesian tooltip to joint angles and the other way round

        Args:
            req(motorcortex.Request): reference to a Request instance
            motorcortex_types(motorcortex.MessageTypes): reference to a MessageTypes instance
    """
    def __init__(self, req: motorcortex.Request, motorcortex_types: motorcortex.MessageTypes) -> None: ...
    def calcCartToJointPose(self, cart_coord: list[float] | None = None, ref_joint_coord_rad: list[float] | None = None, system_id: int | None = None) -> motorcortex.ParameterTree:
        """Converts Cartesian tooltip pose to joint coordinates

            Args:
                cart_coord(list(double)): Cartesian coordinates of the tooltip
                ref_joint_coord_rad(list(double)): actual joint coordinates, rad

            Returns:
                motion_spec.CartToJoint: Joint angles, which correspond to Cartesian coordinates,
                with respect to actual joint positions.

        """
    def calcJointToCartPose(self, joint_coord_rad: list[float] | None = None, cart_coord: list[float] | None = None, system_id: int | None = None) -> motorcortex.ParameterTree:
        """Converts joint coordinates to Cartesian tooltip pose.

            Args:
                joint_coord_rad(list(double)): joint coordinates, rad
                cart_coord(list(double)): actual Cartesian tooltip pose

            Returns:
                motion_spec.JointToCart: Cartesian tooltip pose, which correspond to joint angles,
                with respect to the actual pose.

        """

class MotionProgram:
    """Class represents a motion program of the manipulator

        Args:
            req(motorcortex.Request): reference to a Request instance
            motorcortex_types(motorcortex.MessageTypes): reference to a MessageTypes instance
    """
    def __init__(self, req: motorcortex.Request, motorcortex_types: motorcortex.MessageTypes, use_system_id: bool = False) -> None: ...
    def clear(self) -> None:
        """Clears all commands in the program"""
    def addCommand(self, command: object, type: object) -> None:
        """Adds a command to the program

            Args:
                command(motion_spec.MotionCommand): motion command from motionSL.proto
                type(motion_spec.MOTIONTYPE): type of the motion command
        """
    def addMoveC(self, waypoint_list: list[Waypoint], angle: float, velocity: float = 0.1, acceleration: float = 0.2, rotational_velocity: float = 3.18, rotational_acceleration: float = 6.37, ref_joint_coord_rad: list[float] | None = None) -> None:
        """Adds a MoveC(circular move) command to the program

            Args:
                waypoint_list(list(WayPoint)): a list of waypoints
                angle(double): rotation angle, rad
                velocity(double): maximum velocity, m/sec
                acceleration(double): maximum acceleration, m/sec^2
                rotational_velocity(double): maximum joint velocity, rad/sec
                rotational_acceleration(double): maximum joint acceleration, rad/sec^2
                ref_joint_coord_rad: reference joint coordinates for the first waypoint

        """
    def createMoveC(self, waypoint_list: list[Waypoint], angle: float, velocity: float = 0.1, acceleration: float = 0.2, rotational_velocity: float = 3.18, rotational_acceleration: float = 6.37, ref_joint_coord_rad: list[float] | None = None) -> Any:
        """Creates a MoveC(circular move) command to the program

        Args:
            waypoint_list(list(WayPoint)): a list of waypoints
            angle(double): rotation angle, rad
            velocity(double): maximum velocity, m/sec
            acceleration(double): maximum acceleration, m/sec^2
            rotational_velocity(double): maximum joint velocity, rad/sec
            rotational_acceleration(double): maximum joint acceleration, rad/sec^2
            ref_joint_coord_rad: reference joint coordinates for the first waypoint

        Returns:
            motion_spec.MoveC: returns MoveC command
        """
    def addMoveL(self, waypoint_list: list[Waypoint], velocity: float = 0.1, acceleration: float = 0.2, rotational_velocity: float = 3.18, rotational_acceleration: float = 6.37, ref_joint_coord_rad: list[float] | None = None) -> None:
        """Adds a MoveL(Linear move) command to the program

            Args:
                waypoint_list(list(WayPoint)): a list of waypoints
                velocity(double): maximum velocity, m/sec
                acceleration(double): maximum acceleration, m/sec^2
                rotational_velocity(double): maximum joint velocity, rad/sec
                rotational_acceleration(double): maximum joint acceleration, rad/sec^2
                ref_joint_coord_rad: reference joint coordinates for the first waypoint

        """
    def createMoveL(self, waypoint_list: list[Waypoint], velocity: float = 0.1, acceleration: float = 0.2, rotational_velocity: float = 3.18, rotational_acceleration: float = 6.37, ref_joint_coord_rad: list[float] | None = None) -> Any:
        """Adds a MoveL(Linear move) command to the program

            Args:
                waypoint_list(list(WayPoint)): a list of waypoints
                velocity(double): maximum velocity, m/sec
                acceleration(double): maximum acceleration, m/sec^2
                rotational_velocity(double): maximum joint velocity, rad/sec
                rotational_acceleration(double): maximum joint acceleration, rad/sec^2
                ref_joint_coord_rad: reference joint coordinates for the first waypoint

            Returns:
                motion_spec.MoveL: returns MoveL command
        """
    def addComposedCartMove(self, cart_move_list: list[Any]) -> None: ...
    def addMoveJ(self, waypoint_list: list[Waypoint], rotational_velocity: float = 3.18, rotational_acceleration: float = 6.37) -> None:
        """Adds MoveJ(Joint move) command to the program

            Args:
                waypoint_list(list(WayPoint)): a list of waypoints
                rotational_velocity(double): maximum joint velocity, rad/sec
                rotational_acceleration(double): maximum joint acceleration, rad/sec^2

        """
    def addWait(self, timeout_s: float, path: str | None = None, value: float = 1) -> None:
        """Adds Wait command to the program

            Args:
                timeout_s(double): time to wait in seconds
                path(string): path to the parameter that will be compared to value
                value(double): value that the parameter is compared to
        """
    def createSetType(self, value: float | int | bool) -> tuple[object, object]:
        """
        Create the appropriate Set command and type for the given value type.

        Args:
            value (float | int | bool): The value to set. Determines the type of Set command.

        Returns:
            tuple: (Set command object, Set type enum)

        Raises:
            TypeError: If value is not a float, int, or bool.
        """
    def addSet(self, path: str, value: float | int | bool) -> None:
        """
        Add a Set command to the motion program for the given path and value.

        Args:
            path (str): The parameter path to set.
            value (float | int | bool): The value to set at the path.
        """
    def generateMessage(self, program_name: str = 'Undefined', system_id: int = 0) -> object:
        """
        Generate the motion program message for sending to the robot.

        Args:
            program_name (str): Name of the program.
            system_id (int): System ID for multi-robot setups.

        Returns:
            object: The motion program message object.
        """
    def send(self, program_name: str = 'Undefined', system_id: int = 0) -> motorcortex.ParameterTree:
        """Sends program to the robot

            Args:
                program_name(str): program name

        """
