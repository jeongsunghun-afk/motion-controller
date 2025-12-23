"""
For this example the basic Motorcortex Anthropomorphic Robot application is used. 
You can download it from the Motorcortex Store. 
Make sure to have the Motorcortex Anthropomorphic Robot application running and that you can connect to it using the DESK-Tool.

This example demonstrates how to create a custom button in the GUI that resets a counter in the script.

Add this to the end of the parameters.json file in the config/user folder of the Motorcortex Anthropomorphic Robot application:

{
      "Name": "GUI",
      "Children": [
        {
          "Name": "PythonScript01",
          "Children": [
            {
              "Name": "resetButton",
              "Type": "bool, input",
              "Value": 0
            },
            {
              "Name": "StartButton",
              "Type": "bool, input",
              "Value": 0
            },
            {
              "Name": "Counter",
              "Type": "int,input",
              "Value": 0
            }
          ]
        }
      ]
    }
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

from src.mcx_client_app import McxClientApp, McxClientAppConfiguration, ThreadSafeValue, McxClientAppThread
from motorcortex import Subscription

class Button:
    """
      Class to handle a button with rising and falling edge detection.
      
      Attributes:
          param (str): The parameter path of the button.
          subscription (Subscription): The subscription object for the button.
          state (ThreadSafeValue[bool]): The current state of the button (pressed or not).
          raising_edge_callback (callable): Callback function to call on rising edge (button press).
          falling_edge_callback (callable): Callback function to call on falling edge (button release).
    """
    def __init__(self, param: str, raising_edge_callback: callable = lambda: None, falling_edge_callback: callable = lambda: None):
        """Initialize the Button with parameter path and callbacks.
        
        Args:
            param (str): The parameter path of the button.
            raising_edge_callback (callable): Callback function to call on rising edge (button press).
            falling_edge_callback (callable): Callback function to call on falling edge (button release).
        """
        
        self.param: str = param
        self.subscription: Subscription = None
        self.state: ThreadSafeValue[bool] = ThreadSafeValue(False)
        self.__state_saved: bool = False
        self.raising_edge_callback: callable = raising_edge_callback
        self.falling_edge_callback: callable = falling_edge_callback
        self._clicked: ThreadSafeValue[bool] = ThreadSafeValue(False) # To track click events if polling happens slower than button presses

    def subscription_callback(self, msg: list) -> None:
        """Callback for button press - only trigger on rising edge (0 -> 1). (Happens in the subscription thread)"""
        value = msg[0].value[0]
        if value != 0 and not self.state.get():  # Button pressed (rising edge)
            self.state.set(True)
            self._clicked.set(True)  # Mark a click event
        elif value == 0 and self.state.get():  # Button released (falling edge)
            self.state.set(False)

    def poll(self) -> None:
        """Poll the button state and call the appropriate callbacks on edge detection."""
        # Always detect a click, even if it was very fast
        if self._clicked.get():
            self.raising_edge_callback()
            self._clicked.set(False)
        # Optionally, handle falling edge as before
        current_state = self.state.get()
        if not current_state and self.__state_saved:
            self.falling_edge_callback()
            self.__state_saved = False
        elif current_state and not self.__state_saved:
            self.__state_saved = True

class CustomButtonApp(McxClientAppThread):
    """
    Application that counts and prints the counter value, resetting it when the custom button is pressed.
    """
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        self.reset_button: Button = Button(
            param = 'root/UserParameters/GUI/PythonScript01/resetButton',
            raising_edge_callback = self.reset_counter
        )
        self.counter: int = 0
        
    
    def startOp(self) -> None:
        """
        Subscribe to button updates.
        """
        self.reset_button.subscription = self.sub.subscribe(
            'root/UserParameters/GUI/PythonScript01/resetButton', 
            "Group1", 
            frq_divider=10 
        )
        self.reset_button.subscription.notify(self.reset_button.subscription_callback)
        self.req.setParameter('root/UserParameters/GUI/PythonScript01/Counter', 0).get()
        
    def reset_counter(self) -> None:
      logging.info("Counter reset!")
      self.counter = 0
      # self.req.setParameter('root/UserParameters/GUI/PythonScript01/resetButton', 0).get()

    def iterate(self) -> None:
        """
        Increment counter and check for reset button press.
        """
        self.counter += 1
        print(f"Counter: {self.counter}")
        self.req.setParameter('root/UserParameters/GUI/PythonScript01/Counter', self.counter).get()
        
        self.reset_button.poll()
        
        self.wait(1)  # Wait 1 second between increments

if __name__ == "__main__":
    # client_options = McxClientAppConfiguration.from_json("config.json")
    client_options = McxClientAppConfiguration(
        login="",
        password="",
        target_url="wss://",
        start_stop_param="root/UserParameters/GUI/PythonScript01/StartButton"
    )

    app = CustomButtonApp(client_options)
    app.run()