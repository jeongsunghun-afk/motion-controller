from robot_control.robot_command import RobotCommand as RobotCommand
from robot_control.system_defs import InterpreterEvents as InterpreterEvents, InterpreterStates as InterpreterStates

def isEqual(list_of_values: list, objective_value: int | float | str | bool) -> bool:
    """Checks if all the values in the list are equal to the objective value.

    Args:
        list_of_values(list(any)): list of the values to compare
        objective_value(any): an objective value

    Returns:
        bool: True if operation all is equal, False if not

    """

class MultiRobotCommand:
    """Class represents a state machine of the multiple robot arms.

        Args:
            req(motorcortex.Request): reference to a Request instance
            motorcortex_types(motorcortex.MessageTypes): reference to a MessageTypes instance
            systems(list(int)): a list of systems id

    """
    def __init__(self, req: motorcortex.Request, motorcortex_types: motorcortex.MessageTypes, systems_id: list[int] | None = None) -> None: ...
    def play(self, systems_id: list[int] | None = None, wait_time: float = 1.0) -> list:
        """Plays the program.

            Args:
                wait_time(double): short delay after which actual state of the interpreter is requested
                systems_id(list(int)): an optional list of the systems id, a subset of the object defined list

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def pause(self, systems_id: list[int] | None = None, wait_time: float = 1.0) -> list:
        """Plays the program.

            Args:
                wait_time(double): short delay after which actual state of the interpreter is requested
                systems_id(list(int)): an optional list of the systems id, a subset of the object defined list

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def getState(self, systems_id: list[int] | None = None) -> list:
        """Get actual state of the program interpreter.
        
            Args:
                systems_id(list(int)): an optional list of the systems id, a subset of the object defined list

            Returns:
                InterpreterStates: actual state of the interpreter

        """
    def engage(self) -> bool:
        """Switch robot to Engage state.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def stop(self, systems_id: list[int] | None = None, wait_time: float = 1.0) -> list:
        """Stop the program.

            Args:
                systems_id(list(int)): an optional list of the systems id, a subset of the object defined list
                wait_time(double): short delay after which actual state of the interpreter is requested

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def reset(self, systems_id: list[int] | None = None, wait_time: float = 1.0) -> list:
        """Stop the program and clear the interpreter buffer.

            Args:
                systems_id(list(int)): an optional list of the systems id, a subset of the object defined list
                wait_time(double): short delay after which actual state of the interpreter is requested

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def moveToStart(self, timeout_s: float, systems_id: list[int] | None = None) -> list:
        """Move arm to the start of the program.

            Args:
                timeout_s(double): timeout in seconds
                systems_id(list(int)): an optional list of the systems id, a subset of the object defined list

            Returns:
                bool: True if operation is completed, False if failed

        """
    def system(self, system: int) -> RobotCommand:
        """Move arm to the start of the program.

            Args:
                system(int): id of the system

            Returns:
                RobotCommand: returns a robot command instance for specified system id

        """
