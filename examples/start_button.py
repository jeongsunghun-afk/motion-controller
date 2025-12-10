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
from mcx_client_app import McxClientApp, MCXClientAppOptions

if __name__ == '__main__':
    def action(app: McxClientApp) -> None:
        """
        Example user action: wait for 5 seconds.
        
        Args:
            app (McxClientApp): The app instance.
        """
        logging.info("Action started - waiting 5 seconds...")
        app.wait(5)
        logging.info("Action complete.")
        
    def exit(app: McxClientApp) -> None:
        """
        Example exit action.
        
        Args:
            app (McxClientApp): The app instance.
        """
        app.wait(1)
        logging.info("Exit callback - cleaning up before disconnect.")

    new_options = MCXClientAppOptions(
        login="",
        password="",
        target_url="",
        start_stop_param="root/UserParameters/GUI/PythonScript01/StartStop"
    )

    app = McxClientApp(new_options)
    app.run(action_callback=action, exit_callback=exit)

