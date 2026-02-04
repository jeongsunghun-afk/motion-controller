"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.

This example shows how to use the commandWord parameter to reset a counter when a specific command is received.
The commandWord parameter is a built-in service parameter that allows external systems to send commands to the service.

In `services_config.json`, the Counter parameter is defined:
```json
{
    "Name": "CustomButtonExample",
    "Enabled": true,
    "Parameters": {
    "Version": "1.0",
    "Children": [
        {
        "Name": "Counter",
        "Type": "int, parameter_volatile",
        "Value": 0
        }
    ]
    },
    "Config": {
    "login": "admin",
    "password": "vectioneer",
    "target_url": "wss://192.168.2.100",
    "autoStart": true
    },
    "Watchdog": {
    "Enabled": true,
    "Disabled": true,
    "high": 2000000,
    "tooHigh": 5000000
    }
}
```

The commandWord parameter is automatically created at `root/Services/{ServiceName}/commandWord`.
Send a command by setting commandWord to a specific value (e.g., 1 for reset).
"""
#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

import sys
from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO)

# Add parent directory to path to import mcx_client_app
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcx_client_app import McxClientApp, McxClientAppConfiguration
from src.mcx_client_app.ChangeDetector import ChangeDetector
import motorcortex

class CustomButtonApp(McxClientApp):
    """
    Application that counts and prints the counter value, handling commands when commandWord changes.
    
    This example demonstrates using the ChangeDetector class to monitor the commandWord parameter
    and process commands only when the value changes.
    """
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.command_detector: ChangeDetector = ChangeDetector()
        self.counter: int = 0
        self.command_subscription = None
    
    def startOp(self) -> None:
        """
        Subscribe to commandWord updates and initialize counter.
        """
        # Subscribe to commandWord parameter
        self.command_subscription = self.sub.subscribe(
            [f'{self.options.get_parameter_path}/commandWord'],
            "commandWord_group", 
            frq_divider=10 
        )
        result = self.command_subscription.get()
        if result and result.status == motorcortex.OK:
            self.command_subscription.notify(self._on_command_update)
        
        # Initialize counter parameter
        self.req.setParameter(f'{self.options.get_service_parameter_path}/Counter', 0).get()
    
    def _on_command_update(self, msg) -> None:
        """
        Callback for commandWord updates (runs in subscription thread).
        Just updates the detector value.
        """
        value = msg[0].value[0]
        self.command_detector.set_value(value)

    def iterate(self) -> None:
        """
        Increment counter and check for commandWord changes.
        """
        
        # Check if commandWord changed and process command
        if self.command_detector.has_changed(trigger_on_zero=False):
            value = self.command_detector.get_value()
            logging.info(f"Command received: {value}")
            
            if value == 1:
                logging.info("Resetting counter!")
                self.counter = -1
            elif value == 2:
                logging.info("Doubling counter!")
                self.counter *= 2

            self.req.setParameter(f"{self.options.get_parameter_path}/commandWord", 0)

        self.counter += 1
        print(f"Counter: {self.counter}")
        self.req.setParameter(f'{self.options.get_service_parameter_path}/Counter', self.counter).get()
        
        self.wait(1.0)

if __name__ == "__main__":
    client_options = McxClientAppConfiguration(
        name="CustomButtonExample"
    )
    client_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",  # This is only needed when deployed on a Motorcortex controller. If only locally running, you can set it to None.
        non_deployed_config="examples/services_config.json"
    )
    client_options.load_config()

    app = CustomButtonApp(client_options)
    app.run()