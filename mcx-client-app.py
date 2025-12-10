import logging
from mcx_client_app import McxClientApp, MCXClientAppOptions, StopSignal

if __name__ == '__main__':
    def example_action(app: McxClientApp) -> None:
        """
        Example user action: sleep for 5 seconds.
        
        Args:
            app (McxClientApp): The app instance.
        """
        logging.info("Sleeping for 5 seconds...")
        app.wait(5)
        logging.info("Action complete.")
        
    def create(app: McxClientApp) -> None:
        """
        Example initialization action.
        
        Args:
            app (McxClientApp): The app instance.
        """
        app.newObject = True
        logging.info("Initialization action.")
        
    def startOp(app: McxClientApp) -> None:
        """
        Example start operation action.
        
        Args:
            app (McxClientApp): The app instance.
        """
        app.req.setParameter("root/Operations/StartOperation", 1).get()
        logging.info("Start operation action.")


    new_options = MCXClientAppOptions(
        login ="",
        password="",
        target_url="",
        start_stop_param="root/UserParameters/GUI/PythonScript01/StartStop",
    )

    app = McxClientApp(new_options, create=create)
    app.run(action_callback=example_action, startOp_callback=startOp)
