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
from .McxClientAppConfiguration import McxClientAppOptions
import traceback

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
        self.running: ThreadSafeValue = ThreadSafeValue(False)
        self.__running_subscription: TypingOptional[motorcortex.Subscription] = None
        
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

    def wait_for(
        self,
        param: str,
        value: object,
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
            operat (str): Comparison operator as string (==, !=, <, <=, >, >=, in).
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
    
    def _running_callback(self, msg) -> None:
        """
        Callback for control parameter changes (start/stop and/or state).
        (Happens in subscription thread.)
        """
        # Determine if we should be running
        should_run = True
        
        # Parse message based on subscription layout
        if self.options.start_stop_param and self.options.allowed_states:
            # Both parameters subscribed: [start_stop, state]
            start_stop_value = msg[0].value[0]
            state_value = msg[1].value[0]
            
            should_run = (start_stop_value != 0)
            allowed_values = [s.value for s in self.options.allowed_states]
            should_run = should_run and (state_value in allowed_values)
            
        elif self.options.start_stop_param:
            # Only start/stop parameter
            start_stop_value = msg[0].value[0]
            should_run = (start_stop_value != 0)
            
        elif self.options.allowed_states:
            # Only state parameter
            state_value = msg[0].value[0]
            allowed_values = [s.value for s in self.options.allowed_states]
            should_run = (state_value in allowed_values)
        
        # Update running state if changed
        if self.running.get() != should_run:
            logging.debug(f"Running state changed to {should_run}")
            self.running.set(should_run)
            
    def _setupControlSubscription(self) -> None:
        """Set up single subscription for control parameters (start/stop and/or state).

        This prepares the start/stop parameter (if provided) and subscribes to the
        relevant control parameters. On successful subscription the internal
        running callback is registered.
        """
        control_params: list[str] = []
        if self.options.start_stop_param:
            try:
                # Ensure the start/stop parameter is initialized to 0
                self.req.setParameter(self.options.start_stop_param, 0).get()
            except Exception as e:
                tb = traceback.format_exc()
                logging.error(f"Failed to initialize start/stop parameter '{self.options.start_stop_param}': {e}\n{tb}")
                raise
            control_params.append(self.options.start_stop_param)

        if self.options.allowed_states:
            control_params.append(self.options.state_param)

        if control_params:
            try:
                self.__running_subscription = self.sub.subscribe(
                    control_params,
                    group_alias=f"{self.__id}_control",
                    frq_divider=100
                )
                result = self.__running_subscription.get()
                if result is not None and result.status == motorcortex.OK:
                    logging.debug(f"Control parameters subscription successful: {control_params}")
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

    def run(self) -> None:
        """
        Run the client application: connect, engage, run iterate, disengage, disconnect.
        
        This method:
        1. Connects to the Motorcortex server
        2. Calls startOp() for initialization
        3. Engages the system
        4. Runs the iterate() method in the main thread
        5. Monitors start/stop signals
        6. Disengages and calls onExit() before disconnecting
        """
        self.connect()
        logging.debug("Connected to Motorcortex server.")

        self._setupControlSubscription()
        
        self.startOp()
        
        # Initialize running state based on current conditions
        if not self.options.start_stop_param and not self.options.allowed_states:
            # No conditions to check, start immediately
            self.running.set(True)
        
        try:
            while True:
                try:
                    
                    logging.info("Waiting for start signal...")
                    # Wait for running to become True
                    while not self.running.get():
                        time.sleep(0.1)
                    
                    logging.info("Running user iterate...")
                    # Run iterate method in the main thread
                    while self.running.get():
                        self.iterate()
                    
                    logging.debug("Stop signal detected. Waiting for next start signal...")
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
        if not self.options.start_stop_param and not self.options.allowed_states:
            # No conditions to check, start immediately
            self.running.set(True)
        
        try:
            while True:
                try:
                    
                    logging.info("Waiting for start signal...")
                    # Wait for running to become True
                    while not self.running.get():
                        time.sleep(0.1)
                    
                    logging.info("Running user iterate in separate thread...")
                    
                    # Start iterate method in a separate thread
                    self._action_thread = threading.Thread(target=self._action_wrapper, daemon=True)
                    self._action_thread.start()
                    
                    # Main thread monitors the running state
                    while self.running.get():
                        time.sleep(0.1)  # Check running state periodically
                    
                    # Stop signal received, stop the iterate thread
                    logging.debug("Stop signal detected in main thread.")
                    if self._action_thread and self._action_thread.is_alive():
                        # Wait for action thread to stop (it should check running regularly)
                        self._action_thread.join(timeout=5.0)
                        if self._action_thread.is_alive():
                            logging.warning("Iterate thread did not stop gracefully within timeout.")
                    
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
        def __init__(self, options: McxClientAppOptions):
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

    options = McxClientAppOptions.from_json('config.json')

    logging.info(f"McxClientAppOptions initialized: {options.as_dict()}")
    app = ExampleApp(options)
    app.run()
