"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.

Start up the robot in the GUI.


This example demonstrates how to move the robot left and right using a simple client application.

In service_config.json, the robot app is added with the following snippet:s
```json
{
    "Name": "StartButtonExample",
    "Enabled": true,
    "Config": {
    "login": "admin",
    "password": "vectioneer",
    "target_url": "wss://192.168.2.100",
    "autoStart": true
    },
    "Watchdog": {
    "Enabled": false,
    "Disabled": true,
    "high": 1000000,
    "tooHigh": 5000000
    }
}
"""

import sys
from pathlib import Path

# Add parent directory to path to import mcx_client_app
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import math
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, StopSignal
from robot_control.motion_program import MotionProgram, Waypoint
from robot_control.robot_command import RobotCommand
from robot_control.system_defs import InterpreterStates


class RobotMotionApp(McxClientApp):
    """
    Application that moves the robot left and right.
    """
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        # Initialize robot as None, will be set in startOp
        self.robot = None
        logging.info("RobotMotionApp initialized.")
    
    def startOp(self) -> None:
        """
        Initialize robot after connection is established.
        """
        # Create RobotCommand object (now req is available)
        self.robot = RobotCommand(self.req, self.motorcortex_types)
        
        # Engage the robot
        logging.info("Engaging robot...")
        if self.robot.engage():
            logging.info("Robot engaged successfully")
        else:
            logging.error("Failed to engage robot")
            return
        
        # Reset the robot state
        self.robot.stop()
        self.robot.reset()
        
        logging.info("Robot ready for operation.")
    
    def iterate(self) -> None:
        """
        Execute robot motion: move left and right.
        """
        # Define waypoints for left-right motion
        center_pos = Waypoint([0.4, 0.0, 0.35, 0, math.pi, 0])
        left_pos = Waypoint([0.4, 0.15, 0.35, 0, math.pi, 0])
        right_pos = Waypoint([0.4, -0.15, 0.35, 0, math.pi, 0])
        
        # Create motion program
        motion_program = MotionProgram(self.req, self.motorcortex_types)
        motion_program.addMoveL([center_pos], 0.3, 0.5)
        motion_program.addMoveL([left_pos], 0.3, 0.5)
        motion_program.addMoveL([center_pos], 0.3, 0.5)
        motion_program.addMoveL([right_pos], 0.3, 0.5)
        motion_program.addMoveL([center_pos], 0.3, 0.5)
        
        # Send and execute the motion program
        logging.info("Sending motion program...")
        motion_program.send("left_right_motion").get()
        
        # Play the program
        state = self.robot.play()
        if state == InterpreterStates.MOTION_NOT_ALLOWED_S.value:
            logging.info("Robot not at start position, moving to start...")
            if self.robot.moveToStart(10):
                logging.info("Robot at start position, playing program...")
                self.robot.play()
            else:
                logging.error("Failed to move to start position")
                return
        
        logging.info("Motion program executing...")
        self.wait(10)  # Wait for motion to complete
        logging.info("Iteration complete.")
        
    def onExit(self)->None:
        """
        Cleanup before exiting: stop and disengage the robot.
        """
        if self.robot:
            logging.info("Stopping and disengaging robot...")
            self.robot.stop()
            self.robot.disengage()
            logging.info("Robot disengaged.")


if __name__ == '__main__':
    client_options = McxClientAppConfiguration(
        name="RobotAppExample"
    )

    client_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",  # This is only needed when deployed on a Motorcortex controller. If only locally running, you can set it to None.
        non_deployed_config="examples/services_config.json"
    )
    client_options.load_config()


    app = RobotMotionApp(client_options)
    app.run()