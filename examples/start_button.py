"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.

This example demonstrates how to use a start/stop button to control the execution of the client app.

By default `autoStart` is set to `True` in the service configurations, meaning the application will start running immediately after connection.
In this example we set `autoStart` to `False`, meaning the application will wait for the service to be enabled.

In service_config.json, the start button is enabled with the following snippet:
```json
{
    "Name": "StartButtonExample",
    "Enabled": true,
    "Config": {
    "login": "admin",
    "password": "vectioneer",
    "target_url": "wss://192.168.2.100",
    "cert": "examples/mcx.cert.crt",
    "autoStart": false
    },
    "Watchdog": {
    "Enabled": true,
    "Disabled": true,
    "high": 1000000,
    "tooHigh": 5000000
    }
}
"""
#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#


import logging
import sys
from pathlib import Path

# Add parent directory to path to import mcx_client_app
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to show debug messages
logging.basicConfig(level=logging.INFO)

from src.mcx_client_app import McxClientApp, McxClientAppConfiguration


class StartButtonApp(McxClientApp):
    """
    Example application demonstrating start/stop button control.
    """
    def iterate(self) -> None:
        """
        Main iterate: wait for 5 seconds.
        """
        # logging.info("Iterating...")
        self.wait(5)
        pass
    
    def onExit(self) -> None:
        """
        Cleanup before exit.
        """
        self.wait(1)
        logging.info("Exit callback - cleaning up before disconnect.")

if __name__ == '__main__':
    client_options = McxClientAppConfiguration(
        name="StartButtonExample"
    )

    # In the example services_config.json, the start button is enabled: `startButton: true`
    client_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",  # This is only needed when deployed on a Motorcortex controller. If only locally running, you can set it to None.
        non_deployed_config="examples/services_config.json"
    )
    client_options.load_config()

    app = StartButtonApp(client_options)
    app.run()

