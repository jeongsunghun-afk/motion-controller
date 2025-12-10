"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.
"""


import logging
import math
from mcx_client_app import McxClientApp, MCXClientAppOptions, StopSignal
from robot_control.motion_program import MotionProgram, Waypoint
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates

if __name__ == '__main__':
    def action(app: McxClientApp) -> None:
        """
        Example user action: move robot left and right.
        
        Args:
            app (McxClientApp): The app instance.
        """
        robot = app.robot
        
        # Define waypoints for left-right motion
        center_pos = Waypoint([0.4, 0.0, 0.35, 0, math.pi, 0])
        left_pos = Waypoint([0.4, 0.15, 0.35, 0, math.pi, 0])
        right_pos = Waypoint([0.4, -0.15, 0.35, 0, math.pi, 0])
        
        # Create motion program
        motion_program = MotionProgram(app.req, app.motorcortex_types)
        motion_program.addMoveL([center_pos], 0.3, 0.5)
        motion_program.addMoveL([left_pos], 0.3, 0.5)
        motion_program.addMoveL([center_pos], 0.3, 0.5)
        motion_program.addMoveL([right_pos], 0.3, 0.5)
        motion_program.addMoveL([center_pos], 0.3, 0.5)
        
        # Send and execute the motion program
        logging.info("Sending motion program...")
        motion_program.send("left_right_motion").get()
        
        # Play the program
        state = robot.play()
        if state == InterpreterStates.MOTION_NOT_ALLOWED_S.value:
            logging.info("Robot not at start position, moving to start...")
            if robot.moveToStart(10):
                logging.info("Robot at start position, playing program...")
                robot.play()
            else:
                logging.error("Failed to move to start position")
                return
        
        logging.info("Motion program executing...")
        app.wait(10)  # Wait for motion to complete
        logging.info("Action complete.")
        
    def create(app: McxClientApp) -> None:
        """
        Example initialization action.
        
        Args:
            app (McxClientApp): The app instance.
        """
        
        app.robot = None # Placeholder for RobotCommand, will be set in startOp
        
        logging.info("Create callback - initialization.")
        
    def startOp(app: McxClientApp) -> None:
        """
        Example start operation action - runs after connection is established.
        
        Args:
            app (McxClientApp): The app instance.
        """
        # Create RobotCommand object (now req is available)
        app.robot = RobotCommand(app.req, app.motorcortex_types)
        
        # Engage the robot
        logging.info("Engaging robot...")
        if app.robot.engage():
            logging.info("Robot engaged successfully")
        else:
            logging.error("Failed to engage robot")
            return
        
        # Reset the robot state
        app.robot.stop()
        app.robot.reset()
        
        logging.info("Robot ready for operation.")


    new_options = MCXClientAppOptions(
        login ="",
        password="",
        target_url="",
    )

    app = McxClientApp(new_options, create_callback=create)
    app.run(action_callback=action, startOp_callback=startOp)