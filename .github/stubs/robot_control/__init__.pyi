from robot_control import motionSL_pb2 as motionSL_pb2, motionSL_v1_pb2 as motionSL_v1_pb2, nanopb_pb2 as nanopb_pb2
from robot_control.motion_program import MotionProgram as MotionProgram, PoseTransformer as PoseTransformer, Waypoint as Waypoint
from robot_control.robot_command import RobotCommand as RobotCommand
from robot_control.system_defs import InterpreterEvents as InterpreterEvents, InterpreterStates as InterpreterStates, ModeCommands as ModeCommands, Modes as Modes, StateEvents as StateEvents, States as States

def init(motorcortex_types) -> object:
    """
    Initialize Motorcortex protocol buffer types for robot control.

    Args:
        motorcortex_types: An object with a 'load' method to load proto and hash definitions.

    Returns:
        The result of motorcortex_types.load with the loaded proto and hash definitions.
    """
def to_radians(degrees: list[float | int]) -> list[float]:
    """
    Convert a list of angles from degrees to radians.

    Args:
        degrees (List[float | int]): List of angles in degrees.

    Returns:
        List[float]: List of angles in radians.
    """
