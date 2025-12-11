#!/usr/bin/python3

#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
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
from typing import Callable, Optional, TypeVar, Generic
import queue

T = TypeVar('T')

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
class McxClientAppOptions:
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
    
class ThreadSafeValue(Generic[T]):
    """A thread-safe single-value container.
    
    Methods:
        set(value): Set a new value in a thread-safe manner.
        get(): Get the current value.
    """
    def __init__(self, initial_value: T) -> None:
        """Initialize the ThreadSafeValue with an initial value.
        
        Args:
            initial_value (T): The initial value to store.
        """
        self._q: queue.Queue[T] = queue.Queue(maxsize=1)
        self._q.put(initial_value)

    def set(self, value: T) -> None:
        """Set a new value in a thread-safe manner.
        
        Args:
            value (T): The new value to store.
        """
        try:
            self._q.get_nowait()
        except queue.Empty:
            pass
        self._q.put_nowait(value)

    def get(self) -> T:
        """Get the current value.
        
        Returns:
            T: The current value stored in the container.
        """
        return self._q.queue[0]

class McxClientApp:
    """
    Base client application for interacting with a Motorcortex server.
    Provides methods to connect, engage, disengage, and run user-defined actions with state monitoring.
    
    This base class does NOT use a separate thread for the action() method.
    
    To use this class, inherit from it and override the following methods:
        - action(): Main action loop (called repeatedly while running)
        - startOp(): Called after connection is established (optional)
        - onExit(): Called before disconnecting (optional)
    """
    def __init__(self, options: TypingOptional[McxClientAppOptions] = None) -> None:
        """
        Initialize the MCxClientApp.

        Args:
            options (McxClientAppOptions): Optional McxClientAppOptions dataclass with configuration.
        """
        if options is None:
            options = McxClientAppOptions(login="", password="")
        self.options = options
        self.parameter_tree: motorcortex.ParameterTree = motorcortex.ParameterTree()
        self.motorcortex_types: motorcortex.MessageTypes = motorcortex.MessageTypes()
        self.req: TypingOptional[motorcortex.Request] = None
        self.sub: TypingOptional[motorcortex.Subscription] = None
        self.__id = str(uuid.uuid4())
        self.running: ThreadSafeValue = ThreadSafeValue(self.options.start_stop_param is None)
        
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
            if not self.running.get() and not block_stop_signal:
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
            if not self.running.get() and not block_stop_signal:
                logging.warning("STOP")
                raise StopSignal("Received stop signal")
            time.sleep(testinterval)
            if (time.time() > to) and (timeout > 0):
                return False
        return True

    def reset(self) -> None:
        """
        Reset the running flag to False.
        """
        self.running.set(False)

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

    def action(self) -> None:
        """
        Main action loop called repeatedly while the system is running.
        Override this method in your subclass to implement custom behavior.
        
        In the base class, this method runs in the main thread.
        Use wait() or wait_for() methods which will raise StopSignal when stopped.
        """
        raise NotImplementedError("The action() method must be overridden in the subclass.")
    
    def startOp(self) -> None:
        """
        Called after connection is established, before engaging the system.
        Override this method to set parameters or perform initialization.
        """
        pass
    
    def onExit(self) -> None:
        """
        Called before disconnecting from the server.
        Override this method to perform cleanup operations.
        """
        pass

    def run(self) -> None:
        """
        Run the client application: connect, engage, run action, disengage, disconnect.
        
        This method:
        1. Connects to the Motorcortex server
        2. Calls startOp() for initialization
        3. Engages the system
        4. Runs the action() method in the main thread
        5. Monitors start/stop signals
        6. Disengages and calls onExit() before disconnecting
        """
        self.connect()
        logging.info("Connected to Motorcortex server.")
        self.startOp()
        if self.options.start_stop_param:
            self.req.setParameter(self.options.start_stop_param, 0).get()
            start_stop_subscription = self.sub.subscribe(self.options.start_stop_param, group_alias=self.__id, frq_divider=1000)
            if (start_stop_subscription is not None and start_stop_subscription.get().status == motorcortex.OK):
                logging.info("StartStop parameter subscription successful.")
            logging.info("Subscribed to StartStop parameter notifications.")
            start_stop_subscription.notify(self._start_stop_notify)
        
        try:
            self.engage()
            
            while True:
                try:
                    if self.options.start_stop_param:
                        logging.info("Waiting for StartStop parameter to be True...")
                        self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True)
                        self.running.set(True)
                    logging.info("System engaged. Running user action...")
                    
                    # Run action method in the main thread
                    while self.running.get():
                        self.action()
                    
                    logging.info("Stop signal detected. Waiting for next start signal...")
                    # Continue loop to wait for next start signal
                    
                except StopSignal:
                    logging.info("Action received stop signal.")
                    self.running.set(False)
                except KeyboardInterrupt:
                    # Re-raise to outer handler
                    raise
                except Exception as e:
                    logging.error(f"An error occurred in action loop: {e}")
                    self.running.set(False)
                    # Continue loop to allow restart
                    
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Shutting down...")
            self.running.set(False)
        except Exception as e:
            logging.error(f"Critical error: {e}")
            self.running.set(False)
        finally:
            # Clean up
            self.running.set(False)
            
            try:
                self.disengage()
            except Exception as e:
                logging.error(f"Error during disengage: {e}")
            
            try:
                self.onExit()
            except Exception as e:
                logging.error(f"Error during onExit: {e}")
            
            if self.req:
                try:
                    self.req.close()
                except Exception as e:
                    logging.error(f"Error closing request: {e}")
            if self.sub:
                try:
                    self.sub.close()
                except Exception as e:
                    logging.error(f"Error closing subscription: {e}")
            logging.info("Connection closed.")
    
    def _start_stop_notify(self, msg) -> None:
        """
        Notification callback for StartStop parameter changes. 
        (Happens in a different thread.)
        
        Args:
            msg: Message object containing the new value of the StartStop parameter.
        """
        value = msg[0].value[0]
        if self.running.get() != (value != 0):
            logging.info(f"StartStop parameter changed to {value}. Updating running state.")
            self.running.set(value != 0)

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


class McxClientAppThread(McxClientApp):
    """
    Threaded client application for interacting with a Motorcortex server.
    
    This class extends MCxClientApp and runs the action() method in a separate thread,
    allowing the main thread to monitor start/stop signals independently.
    
    To use this class, inherit from it and override the following methods:
        - action(): Main action loop (called repeatedly in a separate thread)
        - startOp(): Called after connection is established (optional)
        - onExit(): Called before disconnecting (optional)
    """
    def __init__(self, options: TypingOptional[McxClientAppOptions] = None) -> None:
        """
        Initialize the McxClientAppThread.

        Args:
            options (McxClientAppOptions): Optional McxClientAppOptions dataclass with configuration.
        """
        super().__init__(options)
        self._action_thread: TypingOptional[threading.Thread] = None
    
    def run(self) -> None:
        """
        Run the client application with action() in a separate thread.
        
        This method:
        1. Connects to the Motorcortex server
        2. Calls startOp() for initialization
        3. Engages the system
        4. Runs the action() method in a separate thread
        5. Main thread monitors start/stop signals
        6. Disengages and calls onExit() before disconnecting
        """
        self.connect()
        logging.info("Connected to Motorcortex server.")
        self.startOp()
        if self.options.start_stop_param:
            self.req.setParameter(self.options.start_stop_param, 0).get()
            start_stop_subscription = self.sub.subscribe(self.options.start_stop_param, group_alias=self._MCxClientApp__id, frq_divider=1000)
            if (start_stop_subscription is not None and start_stop_subscription.get().status == motorcortex.OK):
                logging.info("StartStop parameter subscription successful.")
            logging.info("Subscribed to StartStop parameter notifications.")
            start_stop_subscription.notify(self._start_stop_notify)
        
        try:
            self.engage()
            
            while True:
                try:
                    if self.options.start_stop_param:
                        logging.info("Waiting for StartStop parameter to be True...")
                        self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True)
                        self.running.set(True)
                    logging.info("System engaged. Running user action in separate thread...")
                    print(f"running: {self.running.get()}")
                    
                    # Start action method in a separate thread
                    self._action_thread = threading.Thread(target=self._action_wrapper, daemon=True)
                    self._action_thread.start()
                    
                    # Main thread monitors the running state
                    while self.running.get():
                        time.sleep(0.1)  # Check running state periodically
                    
                    # Stop signal received, stop the action thread
                    logging.info("Stop signal detected in main thread.")
                    if self._action_thread and self._action_thread.is_alive():
                        # Wait for action thread to stop (it should check running regularly)
                        self._action_thread.join(timeout=5.0)
                        if self._action_thread.is_alive():
                            logging.warning("Action thread did not stop gracefully within timeout.")
                    
                    logging.info("Action thread stopped. Waiting for next start signal...")
                    # Continue loop to wait for next start signal
                    
                except KeyboardInterrupt:
                    # Re-raise to outer handler
                    raise
                except Exception as e:
                    logging.error(f"An error occurred in action loop: {e}")
                    self.running.set(False)
                    if self._action_thread and self._action_thread.is_alive():
                        self._action_thread.join(timeout=5.0)
                    # Continue loop to allow restart
                    
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Shutting down...")
            self.running.set(False)
        except Exception as e:
            logging.error(f"Critical error: {e}")
            self.running.set(False)
        finally:
            # Clean up: stop action thread if still running
            self.running.set(False)
            if self._action_thread and self._action_thread.is_alive():
                logging.info("Stopping action thread...")
                self._action_thread.join(timeout=5.0)
                if self._action_thread.is_alive():
                    logging.warning("Action thread did not stop within timeout. Thread may remain running.")
            
            try:
                self.disengage()
            except Exception as e:
                logging.error(f"Error during disengage: {e}")
            
            try:
                self.onExit()
            except Exception as e:
                logging.error(f"Error during onExit: {e}")
            
            if self.req:
                try:
                    self.req.close()
                except Exception as e:
                    logging.error(f"Error closing request: {e}")
            if self.sub:
                try:
                    self.sub.close()
                except Exception as e:
                    logging.error(f"Error closing subscription: {e}")
            logging.info("Connection closed.")
    
    def _action_wrapper(self) -> None:
        """
        Wrapper for running action() method in a loop until stopped.
        Runs in a separate thread.
        """
        try:
            while self.running.get():
                self.action()
        except StopSignal:
            logging.info("Action thread received stop signal.")
        except Exception as e:
            logging.error(f"Error in action thread: {e}")
            self.running.set(False)


if __name__ == '__main__':
    class ExampleApp(McxClientAppThread):
        """
        Example application demonstrating threaded inheritance pattern.
        """
        def __init__(self, options: McxClientAppOptions):
            super().__init__(options)
            # Add custom attributes here
            self.custom_counter = 0
            logging.info("ExampleApp initialized.")
        
        def action(self) -> None:
            """
            Main action: sleep for 5 seconds.
            This runs in a separate thread when using McxClientAppThread.
            """
            self.custom_counter += 1
            logging.info(f"Action {self.custom_counter}: Sleeping for 5 seconds...")
            self.wait(5)
            logging.info("Action complete.")
        
        def startOp(self) -> None:
            """
            Initialization after connection.
            """
            # Example: set a parameter
            # self.req.setParameter("root/Operations/StartOperation", 1).get()
            logging.info("Start operation complete.")
        
        def onExit(self) -> None:
            """
            Cleanup before exit.
            """
            logging.info(f"Exiting after {self.custom_counter} actions.")

    options = McxClientAppOptions(
        login="",
        password="",
        target_url="",
    )

    app = ExampleApp(options)
    app.run()
