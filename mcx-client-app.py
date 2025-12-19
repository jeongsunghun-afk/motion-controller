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
              "Name": "Counter",
              "Type": "int,input",
              "Value": 0
            }
          ]
        }
      ]
    }
"""


import logging
from src.mcx_client_app import McxClientApp, McxClientAppOptions, StopSignal, ThreadSafeValue

#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#


class CustomButtonApp(McxClientApp):
    """
    Application that monitors and prints the tool pose.
    """
    def __init__(self, options: McxClientAppOptions):
        super().__init__(options)
        self.buttonSubscription = None
        self.counter: int = 0
        self.__reset: ThreadSafeValue[bool] = ThreadSafeValue(False)
    
    def startOp(self) -> None:
        """
        Subscribe to button updates.
        """
        self.buttonSubscription = self.sub.subscribe(
            'root/UserParameters/GUI/PythonScript01/resetButton', 
            "Group1", 
            frq_divider=10 
        )
        self.buttonSubscription.notify(self.__button_callback)
        self.req.setParameter('root/UserParameters/GUI/PythonScript01/Counter', 0).get()
    
    def __button_callback(self, msg) -> None:
        """Callback for button press - only trigger on rising edge (0 -> 1). (Happens in the subscription thread)"""
        value = msg[0].value[0]
        if value != 0:  # Button pressed (rising edge)
            self.__reset.set(True)

    def __reset_counter(self) -> None:
        self.counter = 0
        self.__reset.set(False)
        self.req.setParameter('root/UserParameters/GUI/PythonScript01/resetButton', 0).get()
    
    def action(self) -> None:
        """
        Increment counter and check for reset button press.
        """
        if self.__reset.get():
            self.__reset_counter()
            print("Counter reset!")
        else:
            self.counter += 1
            print(f"Counter: {self.counter}")
            self.req.setParameter('root/UserParameters/GUI/PythonScript01/Counter', self.counter).get()
        
        self.wait(1)  # Wait 1 second between increments

if __name__ == "__main__":
    client_options = McxClientAppOptions.from_json('config.json')

    app = CustomButtonApp(client_options)
    app.run()