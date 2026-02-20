#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

"""
This is an example client application for Motorcortex.

Add the following json snippet to your Motorcortex service configuration file and deploy to enable this application:
```json
{
    "Name": "mcx-client-app",
    "Enabled": true,
    "Parameters": {
    "Version": "1.0",
    "Children": [
    ]
    },
    "Watchdog": {
    "Enabled": true,
    "Disabled": true,
    "high": 1000000,
    "tooHigh": 5000000
    }
},
```
(The configuration file can be found in `services/services_config.json` in the config folder in the portal: https://app.motorcortex.io/projects/)

"""

import sys
from pathlib import Path
import logging
logging.basicConfig(level=logging.INFO)

from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, ThreadSafeValue

class ExampleMcxClientApp(McxClientApp):
    """
    Application that you can change to your needs.
    """
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        
        # Initiate your variables here
        
    def startOp(self) -> None:
        """
        Subscribe to button updates.
        """
        # Start your subscriptions here and set values after connection is established
        pass

    def iterate(self) -> None:
        """
        Increment counter and check for reset button press.
        """
        logging.info("Client app is running...")
        self.wait(1)  # Wait 1 second between increments
        
    def onExit(self) -> None:
        """
        Clean up on exit.
        """
        # Unsubscribe from subscriptions here
        pass
        
if __name__ == "__main__":
    client_options = McxClientAppConfiguration(name="mcx-client-app")
    client_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",  # This is only needed when deployed on a Motorcortex controller. If only locally running, you can set it to None.
        non_deployed_config="services_config.json"
    )
    client_options.load_config()

    print(f"\nUsing configuration: {client_options}\n\n")

    app = ExampleMcxClientApp(client_options)
    app.run()