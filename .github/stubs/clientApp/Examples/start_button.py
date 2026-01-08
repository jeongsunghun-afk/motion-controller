"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.

A additional userParameter was added to the config of the Motorcortex Anthropomorphic Robot application to act as a start/stop button for the script.

Add this to the end of the parameters.json file in the config/user folder of the Motorcortex Anthropomorphic Robot application:

{
    "Name": "GUI",
    "Children": [
    {
        "Name": "PythonScript01",
        "Children": [
        {
            "Name": "StartStop",
            "Type": "bool, input",
            "Value": 0
        }
        ]
    }
    ]
}

You can start and stop the script by toggling this parameter in the DESK-Tool 
or by adding a button in the GUI that toggles this parameter.
"""


import logging
import sys
from pathlib import Path

# Add parent directory to path to import mcx_client_app
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mcx_client_app import McxClientApp, McxClientAppOptions


class StartButtonApp(McxClientApp):
    """
    Example application demonstrating start/stop button control.
    """
    def action(self) -> None:
        """
        Main action: wait for 5 seconds.
        """
        logging.info("Action started - waiting 5 seconds...")
        self.wait(20)
        logging.info("Action complete.")
    
    def onExit(self) -> None:
        """
        Cleanup before exit.
        """
        self.wait(1)
        logging.info("Exit callback - cleaning up before disconnect.")


if __name__ == '__main__':
    new_options = McxClientAppOptions()
    
    # Update the config paths below to match your deployment requirements
    # deployed_config: Path used when DEPLOYED env var is set (on production systems)
    # non_deployed_config: Path used during local development
    new_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/start_button_app.json",
        non_deployed_config="config.json"
    )
    app = StartButtonApp(new_options)
    app.run()

