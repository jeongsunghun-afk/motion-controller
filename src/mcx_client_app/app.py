#!/usr/bin/python3

#
#   Developer : Philippe Piatkiewitz (philippe.piatkiewitz@vectioneer.com)
#   All rights reserved. Copyright (c) 2024 VECTIONEER.
#

from dataclasses import dataclass
from typing import Optional as TypingOptional
import threading
import uuid

import motorcortex
import logging
logging.basicConfig(level=logging.INFO)
import time
import operator
from typing import Callable, Optional
    

waitForOperators = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}

stateCommand = {
    "DO_NOTHING_E": -1,
    "GOTO_OFF_E": 0,
    "GOTO_IDLE_E": 1,
    "GOTO_ENGAGED_E": 2,
    "GOTO_REFERENCING_E": 4,
    "FORCE_IDLE_E": 10,
    "EMERGENCY_STOP_E": 20,
    "SAVE_CONFIGURATION": 254,
    "ACKNOWLEDGE_ERROR": 255
}

state = {
    "INIT_S": 0,
    "OFF_S": 1,
    "IDLE_S": 2,
    "PAUSED_S": 3,
    "ENGAGED_S": 4,
    "HOMING_S": 5,
    "FORCEDIDLE_S": 6,
    "ESTOP_OFF_S": 7,
    "OFF_TO_IDLE_T": 102,
    "OFF_TO_REFERENCING_T": 105,
    "IDLE_TO_OFF_T": 201,
    "PAUSED_TO_IDLE_T": 302,
    "IDLE_TO_ENGAGED_T": 204,
    "ENGAGED_TO_PAUSED_T": 403,
    "TO_FORCEDIDLE_T": 600,
    "RESET_FORCEDIDLE_T": 602,
    "TO_ESTOP_T": 700,
    "RESET_ESTOP_T": 701
}

class StopSignal(Exception):
    """
    Exception raised when a stop signal is received from the Motorcortex server.
    """
    pass


@dataclass
class MCXClientAppOptions:
    """
    Configuration options for McxClientApp.

    Attributes:
        login (str): Username for authenticating with the Motorcortex server.
        password (str): Password for authenticating with the Motorcortex server.
        target_url (str): WebSocket URL of the Motorcortex server (e.g., 'wss://localhost').
            This is the endpoint used to establish the connection.
        cert (str): Path to the SSL certificate file for secure connection (e.g., 'mcx.cert.crt').
            Required for encrypted communication with the server. This is the fallback if "/etc/ssl/certs/mcx.cert.pem" is not found.
        statecmd_param (str): Parameter path for sending state commands to the server (default: 'root/Logic/stateCommand').
            Used to control the robot or system state.
        state_param (str): Parameter path for reading the current state from the server (default: 'root/Logic/state').
            Used to monitor the robot or system state.
        start_stop_param (str|None): Optional parameter path for start/stop control (default: None).
            If provided, the application will monitor this parameter to start or stop operations.
    """
    login: str
    password: str
    target_url: str = "wss://localhost"
    cert: str = "mcx.cert.crt"
    statecmd_param: str = "root/Logic/stateCommand"
    state_param: str = "root/Logic/state"
    start_stop_param: str|None = None

class McxClientApp:
    """
    Client application for interacting with a Motorcortex server.
    Provides methods to connect, engage, disengage, and run user-defined actions with state monitoring.
    """
    def __init__(self, options: TypingOptional[MCXClientAppOptions] = None, create_callback: Optional[Callable[["McxClientApp"], None]] = None) -> None:
        """
        Initialize the McxClientApp.

        Args:
            options (MCXClientAppOptions): Optional MCXClientAppOptions dataclass with configuration.
            create_callback (Optional[Callable[[McxClientApp], None]]): Optional initialization function called after setup. Use this to add custom attributes.
        """
        if options is None:
            options = MCXClientAppOptions(login="", password="")
        self.options = options
        self.parameter_tree: motorcortex.ParameterTree = motorcortex.ParameterTree()
        self.motorcortex_types: motorcortex.MessageTypes = motorcortex.MessageTypes()
        self.req: TypingOptional[motorcortex.Request] = None
        self.sub: TypingOptional[motorcortex.Subscription] = None
        self.__id = str(uuid.uuid4())
        self._running: bool = self.options.start_stop_param is None
        
        if create_callback is not None:
            create_callback(self)
        
    def connect(self) -> None:
        """
        Establish a connection to the Motorcortex server and set up subscriptions.
        Raises:
            Exception: If connection fails.
        """
        try:
            self.req, self.sub = motorcortex.connect(
                self.options.target_url,
                self.motorcortex_types,
                self.parameter_tree,
                certificate=self.__get_cert_path(),
                timeout_ms=10000,
                login=self.options.login,
                password=self.options.password,
                reconnect=True
            )
        except Exception as e:
            logging.error(f"Failed to connect to {self.options.target_url}. Exiting. Error: {e}")
            raise

    def wait_for(
        self,
        param: str,
        value: object = True,
        index: int = 0,
        timeout: float = 30,
        testinterval: float = 0.2,
        operat: str = "==",
        block_stop_signal: bool = False
    ) -> bool:
        """
        Wait for a parameter to meet a certain condition, or until timeout or stop signal.

        Args:
            param (str): Parameter name to monitor.
            value (object): Value to compare against.
            index (int): Index in the parameter value array.
            timeout (float): Timeout in seconds. -1 or 0 for infinite.
            testinterval (float): Polling interval in seconds.
            operat (str): Comparison operator as string (==, !=, <, <=, >, >=).
            block_stop_signal (bool): If True, ignore stop signal.

        Returns:
            bool: True if condition met, False if timeout.

        Raises:
            StopSignal: If stop signal is received and not blocked.
        """
        to = time.time() + timeout if timeout > 0 else float('inf')
        op_func = waitForOperators[operat]
        logging.info(f"Waiting for {param} {operat} {value}")
        while not op_func(self.req.getParameter(param).get().value[index], value):
            if not self._running and not block_stop_signal:
                logging.warning("STOP")
                raise StopSignal("Received stop signal")
            time.sleep(testinterval)
            if (time.time() > to) and (timeout > 0):
                logging.warning("Timeout")
                return False
        return True

    def wait(
        self,
        timeout: float = 30,
        testinterval: float = 0.2,
        block_stop_signal: bool = False
    ) -> bool:
        """
        Wait for a specified timeout, or until stop signal is received.

        Args:
            timeout (float): Timeout in seconds. -1 or 0 for infinite.
            testinterval (float): Polling interval in seconds.
            block_stop_signal (bool): If True, ignore stop signal.

        Returns:
            bool: True if waited full timeout, False if timeout occurred.

        Raises:
            StopSignal: If stop signal is received and not blocked.
        """
        to = time.time() + timeout if timeout > 0 else float('inf')
        while True:
            if not self._running and not block_stop_signal:
                logging.warning("STOP")
                raise StopSignal("Received stop signal")
            time.sleep(testinterval)
            if (time.time() > to) and (timeout > 0):
                return False
        return True

    def reset(self) -> None:
        """
        Reset the running flag to True.
        """
        self._running = False

    def engage(self) -> None:
        """
        Command the system to the ENGAGED state and wait until it is engaged.
        """
        self.req.setParameter(self.options.statecmd_param, stateCommand["GOTO_ENGAGED_E"]).get()
        self.wait_for(self.options.state_param, state["ENGAGED_S"], block_stop_signal=True)

    def disengage(self) -> None:
        """
        Command the system to the OFF state and wait until it is off.
        """
        self.req.setParameter(self.options.statecmd_param, stateCommand["GOTO_OFF_E"]).get()
        self.wait_for(self.options.state_param, state["OFF_S"], block_stop_signal=True)

    def run(
        self,
        action_callback: Callable[["McxClientApp"], None],
        startOp_callback: Optional[Callable[["McxClientApp"], None]] = None,
        exit_callback: Optional[Callable[["McxClientApp"], None]] = None
    ) -> None:
        """
        Run the client application: connect, engage, run action, disengage, disconnect.

        Args:
            action_callback (Optional[Callable[[McxClientApp], None]]):
                Function to call when the system is engaged. Receives the app instance.
                Make sure it is interruptible by checking for stop signals.
            startOp_callback (Optional[Callable[[McxClientApp], None]]):
                Function to call after connection is established. Receives the app instance.
                This can be used to set Parameters before starting the main action loop.
            exit_callback (Optional[Callable[[McxClientApp], None]]):
                Function to call before disconnecting. Receives the app instance.
        """
        self.connect()
        logging.info("Connected to Motorcortex server.")
        if startOp_callback is not None:
            startOp_callback(self)
        if self.options.start_stop_param:
            self.req.setParameter(self.options.start_stop_param, 0).get()
            start_stop_subscription = self.sub.subscribe(self.options.start_stop_param, group_alias=self.__id, frq_divider=1000)
            if (start_stop_subscription is not None and start_stop_subscription.get().status == motorcortex.OK):
                logging.info("StartStop parameter subscription successful.")
            logging.info("Subscribed to StartStop parameter notifications.")
            start_stop_subscription.notify(self._start_stop_notify)
        
        while True:
            try:
                self.engage()
                if self.options.start_stop_param:
                    logging.info("Waiting for StartStop parameter to be True...")
                    self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True)
                    self._running = True
                logging.info("System engaged. Running user action...")
                print(f"running: {self._running}")
                while self._running:
                    action_callback(self)
                    print(f"running: {self._running}")
                else:
                    print(f"running: {self._running}")
                    raise StopSignal("Received stop signal")
            except StopSignal:
                logging.info("Stop signal received. Disengaging...")
                self.reset()
                self.disengage()
            except Exception as e:
                logging.error(f"An error occurred: {e}")
            finally:
                if exit_callback is not None:
                    exit_callback(self)
                if self.req:
                    self.req.close()
                if self.sub:
                    self.sub.close()
                logging.info("Connection closed.")
                break
            
    def _start_stop_notify(self, msg) -> None:
        """
        Notification callback for StartStop parameter changes. 
        (Happens in a different thread.)
        
        Args:
            msg: Message object containing the new value of the StartStop parameter.
        """
        value = msg[0].value[0]
        if self._running != value != 0:
            logging.info(f"StartStop parameter changed to {value}. Updating running state.")
            self._running = value != 0

    def __get_cert_path(self) -> str:
        """
        Get the certificate path, checking default locations.

        Returns:
            str: Path to the certificate file.
        """
        import os
        default_path = "/etc/ssl/certs/mcx.cert.pem"
        if os.path.isfile(default_path):
            return default_path
        return self.options.cert

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

    app = McxClientApp(create=create)
    app.run(action_callback=example_action, startOp_callback=startOp)
