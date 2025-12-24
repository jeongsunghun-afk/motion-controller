from robot_control.system_defs import InterpreterEvents as InterpreterEvents, InterpreterStates as InterpreterStates, ModeCommands as ModeCommands, Modes as Modes, MotionGeneratorStates as MotionGeneratorStates, StateEvents as StateEvents, States as States

class RobotCommand:
    """Class represents a state machine of the robot arm.

        Args:
            req(motorcortex.Request): reference to a Request instance
            motorcortex_types(motorcortex.MessageTypes): reference to a MessageTypes instance
            system_id(int): system id, for example for the dual-arm robot

    """
    def __init__(self, req: object, motorcortex_types: object, system_id: int | None = None) -> None: ...
    def off(self) -> bool:
        """Switch robot to Off state.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def disengage(self) -> bool:
        """Switch robot to Disengage state.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def engage(self) -> bool:
        """Switch robot to Engage state.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def acknowledge(self, timeout_s: float = 20.0) -> bool:
        """Acknowledge the errors and warnings. If robot is in EStop state brings it to the Off state,
        if robot is in ForceDisengaged/ForceIdle state brings it to the Disengaged/Idle state.
        
            Args:
                timeout_s(double): timeout in seconds

            Returns:
                bool: True if operation is completed, False if failed
        """
    def manualCartMode(self) -> bool:
        """Switch robot to a manual Cartesian motion.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def manualJointMode(self) -> bool:
        """Switch robot to a manual joint motion.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def semiAutoMode(self) -> bool:
        """Switch robot to semi-auto mode. Semi-auto moves arm to the target
        when you user holds a button. Semi-auto is active for example during
        move to start of the program.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def toolTipOffset(self, tool_tip_offset: list[float]) -> bool:
        """Update tool-tip offset. Robot should be manual joint mode.

            Args:
                tool_tip_offset(list(double)): new tool tip offset in Cartesian frame of the last segment, rotation
                is defined in Euler ZYX angles.

            Returns:
                bool: True if operation is completed, False if failed

        """
    def moveToPoint(self, target_joint_coord_rad: list[float], v_max: float = 0.5, a_max: float = 1.0) -> bool:
        """Move arm to a specified pose in joint space.

            Args:
                target_joint_coord_rad(list(double)): target pose in joint space, rad
                v_max(double): maximum joint velocity, rad/s
                a_max(double): maximum joint acceleration, rad/s²

            Returns:
                bool: True if operation is completed, False if failed

        """
    def moveToStart(self, timeout_s: float) -> bool:
        """Move arm to the start of the program.

            Args:
                timeout_s(double): timeout in seconds

            Returns:
                bool: True if operation is completed, False if failed

        """
    def play(self, wait_time: float = 1.0) -> object:
        """Plays the program.

            Args:
                wait_time(double): short delay after which actual state of the interpreter is requested

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def pause(self, wait_time: float = 1.0) -> object:
        """Pause the program.

            Args:
                wait_time(double): short delay after which actual state of the interpreter is requested

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def stop(self, wait_time: float = 1.0) -> object:
        """Stop the program.

            Args:
                wait_time(double): short delay after which actual state of the interpreter is requested

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def reset(self, wait_time: float = 1.0) -> object:
        """Stop the program and clear the interpreter buffer.

            Args:
                wait_time(double): short delay after which actual state of the interpreter is requested

            Returns:
                InterpreterStates: actual state of the program interpreter

        """
    def getState(self) -> object:
        """
            Returns:
                InterpreterStates: actual state of the interpreter

        """
