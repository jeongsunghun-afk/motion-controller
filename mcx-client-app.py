import logging
from src.mcx_client_app import McxClientApp, McxClientAppOptions, StopSignal

#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#


class MyRobotApp(McxClientApp):
    """
    Custom robot application.
    Inherit from McxClientApp and override methods to implement custom behavior.
    """
    def __init__(self, options: McxClientAppOptions):
        super().__init__(options)
        # Add your custom attributes here
        self.action_count = 0
        logging.info("MyRobotApp initialized.")
    
    def action(self) -> None:
        """
        Main action loop - executed repeatedly while running.
        This runs in a separate thread.
        """
        self.action_count += 1
        logging.info(f"Action #{self.action_count}: Sleeping for 5 seconds...")
        self.wait(5)
        logging.info("Action complete.")
    
    def startOp(self) -> None:
        """
        Called after connection is established.
        Use this to set parameters or perform initialization.
        """
        logging.info("Start operation - setting up parameters...")
        # Example: self.req.setParameter("root/SomeParameter", value).get()
    
    def onExit(self) -> None:
        """
        Called before disconnecting.
        Use this for cleanup operations.
        """
        logging.info(f"Exiting after {self.action_count} actions performed.")


if __name__ == '__main__':
    options = McxClientAppOptions(
        login="",
        password="",
        target_url="",
        # start_stop_param="root/UserParameters/GUI/PythonScript01/StartStop"
    )

    app = MyRobotApp(options)
    app.run()
