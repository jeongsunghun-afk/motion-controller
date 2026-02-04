#!/usr/bin/python3

#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

from dataclasses import dataclass, field
from typing import Optional as TypingOptional
import threading
import uuid

import motorcortex
import logging
logging.basicConfig(level=logging.INFO)
import time
import operator
from typing import Optional, TypeVar, Generic
import copy
from .McxClientAppConfiguration import McxClientAppConfiguration
from .McxWatchdog import McxWatchdog
from .McxErrorHandler import McxErrorHandler
import traceback
from enum import Enum

T = TypeVar('T')


waitForOperators = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "in": lambda a, b: a in b,
}

def map_subscription_reply(msg, param_layout: list[str]) -> dict:
    """
    Map subscription reply message to parameter path -> value dictionary.

    Args:
        msg: Subscription reply message (list of parameter values).
        param_layout (list[str]): List of parameter paths corresponding to the message.
    Returns:
        dict: Dictionary mapping parameter paths to their values.
    """
    if (len(msg) != len(param_layout)):
        logging.error(f"Message length {len(msg)} does not match parameter layout length {len(param_layout)}")
    assert len(msg) == len(param_layout), "Message length and parameter layout length must match"

    values: dict = {}
    for i, path in enumerate(param_layout):
        values[path] = msg[i].value
    return values


class StopSignal(Exception):
    """
    Exception raised when a stop signal is received from the Motorcortex server.
    """
    pass

class ThreadSafeValue(Generic[T]):
    """
    Thread-safe single-value container for sharing data between threads.
    Provides get() and set() methods with locking to ensure thread safety.
    """
    def __init__(self, initial_value: Optional[T] = None) -> None:
        self._lock = threading.Lock()
        self.__value = initial_value
        
    def get(self) -> Optional[T]:
        """
        Get the current value in a thread-safe manner.

        Returns:
            The current value.
        """
        with self._lock:
            return copy.deepcopy(self.__value)
        
    def set(self, value: T) -> None:
        """
        Set a new value in a thread-safe manner.

        Args:
            value: The new value to set.
        """
        with self._lock:
            self.__value = copy.deepcopy(value)

class ServiceStatus(Enum):
    """
    Enum representing service status values.
    """
    NOT_RUNNING = 0
    WAITING_TO_START = 1
    RUNNING = 2

class StatusManager:
    """
    Manages status parameters for the McxClientApp.
    """
    def __init__(self, req: motorcortex.Request|None, base_path: str) -> None:
        self.req = req
        self.base_path = base_path
        self.__status: ThreadSafeValue[ServiceStatus] = ThreadSafeValue(ServiceStatus.NOT_RUNNING)

    def set_request(self, req: motorcortex.Request) -> None:
        """
        Set the motorcortex Request object.

        Args:
            req (motorcortex.Request): The request object to set.
        """
        self.req = req

    def set_status(self, value: int) -> None:
        """
        Set a status parameter value.

        Args:
            value (int): Value to set.
        """
        if (self.req is None):
            return
        try:
            status = ServiceStatus(value)
        except ValueError:
            raise ValueError(f"Invalid status value: {value}")
        self.__status.set(ServiceStatus(value))
        param_path = f"{self.base_path}/statusWord"
        self.req.setParameter(param_path, value).get()

    def get_status(self, status_name: str) -> int:
        """
        Get a status parameter value.

        Args:
            status_name (str): Name of the status parameter.

        Returns:
            int: The current value of the status parameter.
        """
        return self.__status.get()

class McxClientApp:
    """
    Base client application for interacting with a Motorcortex server.
    Provides methods to connect, engage, disengage, and run user-defined actions with state monitoring.
    
    This base class does NOT use a separate thread for the iterate() method.
    
    To use this class, inherit from it and override the following methods:
        - iterate(): Main iterate loop (called repeatedly while running)
        - startOp(): Called after connection is established (optional)
        - onExit(): Called before disconnecting (optional)
    """
    def __init__(self, options: McxClientAppConfiguration) -> None:
        """
        Initialize the MCxClientApp.

        Args:
            options (McxClientAppConfiguration): Optional McxClientAppConfiguration dataclass with configuration.
        """
        self.options = options
        if not self.options.has_config:
            logging.warning("No json config has been set!  THIS WILL CAUSE ERRORS WHEN DEPLOYED. Use `set_config_paths()` of `McxClientAppConfiguration` to configure the code for deployment.")
        if not self.options.is_deployed and self.options.deployed_config == None:
            logging.warning("Deployed configuration path not set! THIS WILL CAUSE ERRORS WHEN DEPLOYED.")
        
        self.parameter_tree: motorcortex.ParameterTree = motorcortex.ParameterTree()
        self.motorcortex_types: motorcortex.MessageTypes = motorcortex.MessageTypes()
        self.req: TypingOptional[motorcortex.Request] = None
        self.sub: TypingOptional[motorcortex.Subscription] = None
        self.__id = str(uuid.uuid4())
        self.running: ThreadSafeValue = ThreadSafeValue(False)
        self.__running_subscription: TypingOptional[motorcortex.Subscription] = None
        # layout of the last control subscription (list of param paths)
        self._control_params: list[str] = []

        self.watchdog: McxWatchdog = McxWatchdog(
            watchdog_folder_path=f"{self.options.get_parameter_path}/watchdog", 
            enabled = self.options.enable_watchdog)
        
        self.statusManager = StatusManager(
            req=self.req, 
            base_path=self.options.get_parameter_path)
        
        self.errorHandler = McxErrorHandler(
            error_folder_path=self.options.get_parameter_path + "/error",
            error_reset_parameter=self.options.error_reset_param,
            req=self.req,
            sub=self.sub,
            enabled=self.options.enable_error_handler)
    
        
    def connect(self) -> None:
        """
        Establish a connection to the Motorcortex server and set up subscriptions.
        Raises:
            Exception: If connection fails.
        """
        try:
            self.req, self.sub = motorcortex.connect(
                self.options.ip_address,
                self.motorcortex_types,
                self.parameter_tree,
                certificate=self.options.certificate,
                timeout_ms=3000,
                login=self.options.login,
                password=self.options.password,
                reconnect=True
            )
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Failed to connect to {self.options.ip_address}. Exiting. Error: {e}\nTraceback:\n{tb}")
            raise

        self.watchdog.set_request(self.req)
        self.watchdog.setDisable(False)

        self.statusManager.set_request(self.req)

        self.errorHandler.set_request_and_subscription(self.req, self.sub)
        self.errorHandler.start_subscription()

    def wait_for(
        self,
        param: str,
        value: object,
        index: int = 0,
        timeout: float = 30,
        testinterval: float = 0.2,
        operat: str = "==",
        keep_watchdog: bool = True,
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
            operat (str): Comparison operator as string (==, !=, <, <=, >, >=, in).
            keep_watchdog (bool): If True, keep watchdog alive while waiting.
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
            # Keep the watchdog alive while waiting unless explicitly disabled
            if keep_watchdog and getattr(self, "watchdog", None) is not None:
                try:
                    self.watchdog.iterate()
                except Exception:
                    logging.debug("Watchdog iterate raised an exception, continuing")
            time.sleep(testinterval)
            if (time.time() > to) and (timeout > 0):
                logging.warning("Timeout")
                return False
        return True

    def wait(
        self,
        timeout: float = 30,
        testinterval: float = 0.2,
        keep_watchdog: bool = True,
        block_stop_signal: bool = False
    ) -> bool:
        """
        Wait for a specified timeout, or until stop signal is received.

        Args:
            timeout (float): Timeout in seconds. -1 or 0 for infinite.
            testinterval (float): Polling interval in seconds.
            block_stop_signal (bool): If True, ignore stop signal.
            keep_watchdog (bool): If True, keep watchdog alive while waiting.

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
            # Keep the watchdog alive while waiting unless explicitly disabled
            if keep_watchdog and getattr(self, "watchdog", None) is not None:
                try:
                    self.watchdog.iterate()
                except Exception:
                    logging.debug("Watchdog iterate raised an exception, continuing")
            time.sleep(testinterval)
            if (time.time() > to) and (timeout > 0):
                return False
        return True

    def reset(self) -> None:
        """
        Reset the running flag to False.
        """
        self.running.set(False)
    
    def _running_callback(self, msg:list) -> None:
        """
        Callback for control parameter changes (start/stop and/or state).
        (Happens in subscription thread.)
        """

        result: dict = map_subscription_reply(msg, self._control_params)

        isEnabled: bool = bool(result.get(f"{self.options.get_parameter_path}/enableService", [0])[0])

        # Extract the scalar current state value safely (subscription returns a list/tuple)
        current_state = None
        state_val = result.get(self.options.state_param, None)
        if isinstance(state_val, (list, tuple)) and len(state_val) > 0:
            current_state = state_val[0]
        else:
            current_state = state_val

        allowed_values = [s.value for s in self.options.allowed_states]
        isAllowedState: bool = (current_state in allowed_values) if self.options.allowed_states else True

        should_run = isEnabled and isAllowedState

        if self.running.get() != should_run:
            logging.debug(f"Running state changed to {should_run}")
            self.running.set(should_run)

    def _setupControlSubscription(self) -> None:
        """Set up single subscription for control parameters (start/stop and/or state).

        This prepares the start/stop parameter (if provided) and subscribes to the
        relevant control parameters. On successful subscription the internal
        running callback is registered.
        """
        self._control_params: list[str] = []

        self._control_params.append(f"{self.options.get_parameter_path}/enableService")

        if self.options.allowed_states:
            self._control_params.append(self.options.state_param)

        if self._control_params:
            try:
                self.__running_subscription = self.sub.subscribe(
                    self._control_params,
                    group_alias=f"{self.__id}_control",
                    frq_divider=1000
                )
                result = self.__running_subscription.get()
                if result is not None and result.status == motorcortex.OK:
                    logging.debug(f"Control parameters subscription successful: {self._control_params}")
                    self.__running_subscription.notify(self._running_callback)
                else:
                    logging.error("Failed to subscribe to control parameters.")
            except Exception as e:
                tb = traceback.format_exc()
                logging.error(f"Exception while subscribing to control parameters: {e}\nTraceback:\n{tb}")
                raise

    def iterate(self) -> None:
        """
        Main iterate loop called repeatedly while the system is running.
        Override this method in your subclass to implement custom behavior.
        
        In the base class, this method runs in the main thread.
        Use wait() or wait_for() methods which will raise StopSignal when stopped.
        """
        raise NotImplementedError("The iterate() method must be overridden in the subclass.")
    
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

    def preIterate(self) -> None:
        """
        Called before each iterate() call.
        Override this method to perform actions before each iteration.
        """
        self.statusManager.set_status(ServiceStatus.RUNNING.value)

    def postIterate(self) -> None:
        """
        Called after each iterate() call.
        Override this method to perform actions after each iteration.
        """
        self.statusManager.set_status(ServiceStatus.NOT_RUNNING.value)

    def run(self) -> None:
        """
        Run the client application: connect, engage, run iterate, disengage, disconnect.
        
        This method:
        1. Connects to the Motorcortex server
        2. Calls startOp() for initialization
        3. Runs the iterate() method in the main thread
        4. Monitors start/stop signals
        5. Disengages and calls onExit() before disconnecting
        """
        
        self.connect()
        logging.debug("Connected to Motorcortex server.")

        self._setupControlSubscription()
        
        self.startOp()
        
        # Initialize running state based on current conditions
        try:
            # Ensure it starts as disabled
            print(f"Setting to {f"{self.options.get_parameter_path}/enableService"} to {self.options.autoStart}")
            self.req.setParameter(f"{self.options.get_parameter_path}/enableService", int(self.options.autoStart)).get()
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Failed to set to disable: '{f"{self.options.get_parameter_path}/enableService"}': {e}\n{tb}")
            raise
        
        try:
            while True:
                try:
                    if (not self.running.get()):
                        logging.info("Waiting to start...")
                        self.statusManager.set_status(ServiceStatus.WAITING_TO_START.value)

                    # Wait for running to become True
                    while not self.running.get():
                        self.wait(0.1, block_stop_signal=True)
                    
                    logging.info("Running user iterate...")
                    # Run iterate method in the main thread

                    self.preIterate()
                    while self.running.get():
                        self.iterate()
                        self.watchdog.iterate()
                    self.postIterate()
                    
                    logging.debug("Iterate loop stopped...")
                    # Continue loop to wait for next start signal
                    
                except StopSignal:
                    logging.info("Iterate received stop signal.")
                    self.running.set(False)
                except KeyboardInterrupt:
                    # Re-raise to outer handler
                    raise
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"An error occurred in iterate loop: {e}\nTraceback:\n{tb}")
                    self.running.set(False)
                    # Continue loop to allow restart
                    
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Shutting down...")
            self.running.set(False)
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Critical error: {e}\nTraceback:\n{tb}")
            self.running.set(False)
        finally:
            # Clean up
            self.running.set(False)
            
            try:
                self.postIterate()
                self.onExit()
            except Exception as e:
                tb = traceback.format_exc()
                logging.error(f"Error during onExit: {e}\nTraceback:\n{tb}")
            
            if self.req:
                try:
                    self.req.close()
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"Error closing request: {e}\nTraceback:\n{tb}")
            if self.sub:
                try:
                    self.sub.close()
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"Error closing subscription: {e}\nTraceback:\n{tb}")
            logging.debug("Connection closed.")


class McxClientAppThread(McxClientApp):
    """
    Threaded client application for interacting with a Motorcortex server.
    
    This class extends MCxClientApp and runs the iterate() method in a separate thread,
    allowing the main thread to monitor start/stop signals independently.
    
    To use this class, inherit from it and override the following methods:
        - iterate(): Main iterate loop (called repeatedly in a separate thread)
        - startOp(): Called after connection is established (optional)
        - onExit(): Called before disconnecting (optional)
    """
    def __init__(self, options: TypingOptional[McxClientAppConfiguration] = None) -> None:
        """
        Initialize the McxClientAppThread.

        Args:
            options (McxClientAppConfiguration): Optional McxClientAppConfiguration dataclass with configuration.
        """
        super().__init__(options)
        self._action_thread: TypingOptional[threading.Thread] = None
    
    def run(self) -> None:
        """
        Run the client application with iterate() in a separate thread.
        
        This method:
        1. Connects to the Motorcortex server
        2. Calls startOp() for initialization
        3. Engages the system
        4. Runs the iterate() method in a separate thread
        5. Main thread monitors start/stop signals
        6. Disengages and calls onExit() before disconnecting
        """
        self.connect()
        logging.debug("Connected to Motorcortex server.")
        
        self._setupControlSubscription()
        
        self.startOp()
        
        # Initialize running state based on current conditions
        try:
            # Ensure it starts as disabled according to autoStart
            print(f"Setting to disable: '{f'{self.options.get_parameter_path}/enableService'}' to {not self.options.autoStart}")
            self.req.setParameter(f"{self.options.get_parameter_path}/enableService", int(not self.options.autoStart)).get()
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Failed to set to disable: '{f"{self.options.get_parameter_path}/enableService"}': {e}\n{tb}")
            raise
        
        try:
            while True:
                try:
                    if (not self.options.autoStart and not self.running.get()):
                        logging.info("autoStart not enabled so waiting to start...")
                        self.statusManager.set_status(ServiceStatus.WAITING_TO_START.value)

                    # Wait for running to become True
                    while not self.running.get():
                        time.sleep(0.1)
                    
                    logging.info("Running user iterate in separate thread...")
                    self.preIterate()
                    
                    # Start iterate method in a separate thread
                    self._action_thread = threading.Thread(target=self._action_wrapper, daemon=True)
                    self._action_thread.start()
                    
                    # Main thread monitors the running state
                    while self.running.get():
                        self.watchdog.iterate()
                    
                    # Stop signal received, stop the iterate thread
                    logging.debug("Stop signal detected in main thread.")
                    if self._action_thread and self._action_thread.is_alive():
                        # Wait for action thread to stop (it should check running regularly)
                        self._action_thread.join(timeout=5.0)
                        if self._action_thread.is_alive():
                            logging.warning("Iterate thread did not stop gracefully within timeout.")
                    

                    self.postIterate()
                    logging.debug("Iterate thread stopped. Waiting for next start signal...")
                    # Continue loop to wait for next start signal
                    
                except KeyboardInterrupt:
                    # Re-raise to outer handler
                    raise
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"An error occurred in action loop: {e}\nTraceback:\n{tb}")
                    self.running.set(False)
                    if self._action_thread and self._action_thread.is_alive():
                        self._action_thread.join(timeout=5.0)
                    # Continue loop to allow restart
                    
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Shutting down...")
            self.running.set(False)
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Critical error: {e}\nTraceback:\n{tb}")
            self.running.set(False)
        finally:
            # Clean up: stop iterate thread if still running
            self.running.set(False)
            if self._action_thread and self._action_thread.is_alive():
                logging.debug("Stopping action thread...")
                self._action_thread.join(timeout=5.0)
                if self._action_thread.is_alive():
                    logging.warning("Action thread did not stop within timeout. Thread may remain running.")
            
            try:
                self.onExit()
            except Exception as e:
                tb = traceback.format_exc()
                logging.error(f"Error during onExit: {e}\nTraceback:\n{tb}")
            
            self.errorHandler.stop_subscription()

            if self.req:
                try: 
                    self.req.close()
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"Error closing request: {e}\nTraceback:\n{tb}")
            if self.sub:
                try:
                    self.sub.close()
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"Error closing subscription: {e}\nTraceback:\n{tb}")
            logging.info("Connection closed.")
    
    def _action_wrapper(self) -> None:
        """
        Wrapper for running iterate() method in a loop until stopped.
        Runs in a separate thread.
        """
        try:
            while self.running.get():
                self.iterate()
        except StopSignal:
            logging.info("Iterate thread received stop signal.")
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Error in iterate thread: {e}\nTraceback:\n{tb}")
            self.running.set(False)


if __name__ == '__main__':
    class ExampleApp(McxClientAppThread):
        """
        Example application demonstrating threaded inheritance pattern.
        """
        def __init__(self, options: McxClientAppConfiguration):
            super().__init__(options)
            # Add custom attributes here
            self.custom_counter = 0
            logging.info("ExampleApp initialized.")
        
        def iterate(self) -> None:
            """
            Main iterate: sleep for 5 seconds.
            This runs in a separate thread when using McxClientAppThread.
            """
            self.custom_counter += 1
            logging.info(f"Iterate {self.custom_counter}: Sleeping for 5 seconds...")
            self.wait(5)
            logging.info("Iterate complete.")
        
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
            logging.info(f"Exiting after {self.custom_counter} iterations.")

    options = McxClientAppConfiguration()

    logging.info(f"McxClientAppConfiguration initialized: {options.as_dict()}")
    app = ExampleApp(options)
    app.run()
