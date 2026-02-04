#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

"""
This is an example client application for Motorcortex.

Add the following json snippet to your Motorcortex service configuration file and deploy to enable this application:
```json
{
    "Name": "ErrorExample",
    "Enabled": true,
    "Config": {
    "login": "admin",
    "password": "vectioneer",
    "target_url": "wss://192.168.2.100"
    },
    "Parameters": {
    "Version": "1.0",
    "Children": [
        {
        "Name": "input",
        "Type": "int, input",
        "Value": 0
        }
    ]
    },
    "Watchdog": {
    "Enabled": false,
    "Disabled": true,
    "high": 1000000,
    "tooHigh": 5000000
    }
}
```
(The configuration file can be found in `services/services_config.json` in the config folder in the portal: https://app.motorcortex.io/projects/)

"""

import sys
from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO)
import motorcortex

# Expose package version when running the example script
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, ThreadSafeValue

class ErrorMcxClientApp(McxClientApp):
    """
    Example Motorcortex client application demonstrating error handling.
    1. Monitors an integer input parameter.
    2. Triggers different error levels based on the input value.
    3. Resets the input parameter when the error is acknowledged.
    """
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        
        self.__last_value: int = 0
        
    def startOp(self) -> None:
        """
        Initialize the error handler and set up the acknowledge callback.
        """
        self.errorHandler.set_subsystem_id(1) # Set subsystem ID if needed (Helpful to identify which subsystem the error belongs to)
        self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)

    def on_error_acknowledged(self):
        """
        Callback function when an error is acknowledged.

        Resets the input parameter to 0.
        """
        result = self.req.setParameter(f"{self.options.get_service_parameter_path}/input", 0).get()
        if result is not None and result.status !=  motorcortex.OK:
            logging.error("Failed to reset the button parameter after error acknowledgment.")

        logging.info("Error has been acknowledged by the user!")

    def iterate(self) -> None:
        """
        Monitor the input parameter and trigger errors based on its value.
        """
        result = self.req.getParameter(f"{self.options.get_service_parameter_path}/input").get()
        if result is not None and result.status == motorcortex.OK:
            value = result.value[0]

            if self.__last_value != value: # Rising edge detection
                if value >10 and value <20:
                    logging.info("Triggering WARNING level error.")
                    self.errorHandler.trigger_warning(1001)
                elif value >=20 and value <30:
                    logging.info("Triggering FORCED DISENGAGED level error.")
                    self.errorHandler.trigger_forced_disengage(2001)
                elif value >=30 and value <40:
                    logging.info("Triggering SHUTDOWN level error.")
                    self.errorHandler.trigger_shutdown(3001)
                elif value >=40 and value <50:
                    logging.info("Triggering EMERGENCY level error.")
                    self.errorHandler.trigger_emergency_stop(4001)

                self.__last_value = value
        
if __name__ == "__main__":
    client_options = McxClientAppConfiguration(name="ErrorExample")
    client_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",  # This is only needed when deployed on a Motorcortex controller. If only locally running, you can set it to None.
        non_deployed_config="examples/services_config.json"
    )
    client_options.load_config()

    # print(f"Using configuration: {client_options}")

    app = ErrorMcxClientApp(client_options)
    app.run()