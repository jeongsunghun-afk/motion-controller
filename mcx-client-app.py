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
        print("Client app is running...")
        self.wait(1)  # Wait 1 second between increments
        
    def onExit(self) -> None:
        """
        Clean up on exit.
        """
        # Unsubscribe from subscriptions here
        pass
        
if __name__ == "__main__":
    client_options = McxClientAppConfiguration()
    client_options.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/mcx_client_app.json",
        non_deployed_config="config.json"
    )

    app = ExampleMcxClientApp(client_options)
    app.run()