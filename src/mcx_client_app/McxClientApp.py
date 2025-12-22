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
from .McxClientAppOptions import McxClientAppOptions
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
                self.options.ip_address,
                self.motorcortex_types,
                self.parameter_tree,
                certificate=self.options.certificate,
                timeout_ms=10000,
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
        logging.debug("Connected to Motorcortex server.")
        self.startOp()
        if self.options.start_stop_param:
            self.req.setParameter(self.options.start_stop_param, 0).get()
            start_stop_subscription = self.sub.subscribe(self.options.start_stop_param, group_alias=self.__id, frq_divider=1000)
            if (start_stop_subscription is not None and start_stop_subscription.get().status == motorcortex.OK):
                logging.debug("StartStop parameter subscription successful.")
            logging.debug("Subscribed to StartStop parameter notifications.")
            start_stop_subscription.notify(self._start_stop_notify)
        
        try:
            while True:
                try:
                    # Wait for StartStop and/or allowed states before starting action
                    need_start = bool(self.options.start_stop_param)
                    need_states = bool(self.options.allowed_states)

                    if need_start or need_states:
                        allowed_states = [s.value for s in self.options.allowed_states] if need_states else None
                        self.running.set(False)
                        try:
                            if need_start and need_states:
                                logging.debug("Waiting for StartStop == True and system in allowed states...")
                                # Wait for StartStop to become true
                                self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True, timeout=-1)
                                # Then wait for system state to be one of the allowed states
                                self.wait_for(self.options.state_param, allowed_states, operat="in", block_stop_signal=True, timeout=-1)
                            elif need_start:
                                logging.info("Waiting for StartStop == True...")
                                self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True, timeout=-1)
                            else:
                                logging.info("Waiting for system to be in allowed states...")
                                self.wait_for(self.options.state_param, allowed_states, operat="in", block_stop_signal=True, timeout=-1)

                            # Both conditions satisfied -> start action
                            self.running.set(True)

                        except StopSignal:
                            logging.debug("Stop signal received while waiting. Returning to top-level loop.")
                            self.running.set(False)
                            continue
                    logging.debug("Running user action...")
                    
                    # Run action method in the main thread
                    while self.running.get():
                        # Check if still in allowed states
                        if self.options.allowed_states:
                            current_state = self.req.getParameter(self.options.state_param).get().value[0]
                            if current_state not in [s.value for s in self.options.allowed_states]:
                                logging.warning("System no longer in allowed states. Stopping action.")
                                self.running.set(False)
                                break
                            
                        self.action()
                    
                    logging.debug("Stop signal detected. Waiting for next start signal...")
                    # Continue loop to wait for next start signal
                    
                except StopSignal:
                    logging.info("Action received stop signal.")
                    self.running.set(False)
                except KeyboardInterrupt:
                    # Re-raise to outer handler
                    raise
                except Exception as e:
                    tb = traceback.format_exc()
                    logging.error(f"An error occurred in action loop: {e}\nTraceback:\n{tb}")
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
    
    def _start_stop_notify(self, msg) -> None:
        """
        Notification callback for StartStop parameter changes. 
        (Happens in a different thread.)
        
        Args:
            msg: Message object containing the new value of the StartStop parameter.
        """
        value = msg[0].value[0]
        if self.running.get() != (value != 0):
            logging.debug(f"StartStop parameter changed to {value}. Updating running state.")
            self.running.set(value != 0)


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
        logging.debug("Connected to Motorcortex server.")
        self.startOp()
        if self.options.start_stop_param:
            self.req.setParameter(self.options.start_stop_param, 0).get()
            start_stop_subscription = self.sub.subscribe(self.options.start_stop_param, group_alias=self._MCxClientApp__id, frq_divider=1000)
            if (start_stop_subscription is not None and start_stop_subscription.get().status == motorcortex.OK):
                logging.debug("StartStop parameter subscription successful.")
            logging.debug("Subscribed to StartStop parameter notifications.")
            start_stop_subscription.notify(self._start_stop_notify)
        
        try:
            while True:
                try:
                    # Wait for StartStop and/or allowed states before starting action
                    need_start = bool(self.options.start_stop_param)
                    need_states = bool(self.options.allowed_states)

                    if need_start or need_states:
                        allowed_states = [s.value for s in self.options.allowed_states] if need_states else None
                        self.running.set(False)
                        try:
                            if need_start and need_states:
                                logging.debug("Waiting for StartStop == True and system in allowed states...")
                                # Wait for StartStop to become true
                                self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True, timeout=-1)
                                # Then wait for system state to be one of the allowed states
                                self.wait_for(self.options.state_param, allowed_states, operat="in", block_stop_signal=True, timeout=-1)
                            elif need_start:
                                logging.debug("Waiting for StartStop == True...")
                                self.wait_for(self.options.start_stop_param, 0, operat="!=", block_stop_signal=True, timeout=-1)
                            else:
                                logging.debug("Waiting for system to be in allowed states...")
                                self.wait_for(self.options.state_param, allowed_states, operat="in", block_stop_signal=True, timeout=-1)

                            # Both conditions satisfied -> start action
                            self.running.set(True)

                        except StopSignal:
                            logging.debug("Stop signal received while waiting. Returning to top-level loop.")
                            self.running.set(False)
                            continue
                    
                    logging.debug("Running user action in separate thread...")
                    print(f"running: {self.running.get()}")
                    
                    # Start action method in a separate thread
                    self._action_thread = threading.Thread(target=self._action_wrapper, daemon=True)
                    self._action_thread.start()
                    
                    # Main thread monitors the running state
                    while self.running.get():
                        time.sleep(0.1)  # Check running state periodically
                    
                    # Stop signal received, stop the action thread
                    logging.debug("Stop signal detected in main thread.")
                    if self._action_thread and self._action_thread.is_alive():
                        # Wait for action thread to stop (it should check running regularly)
                        self._action_thread.join(timeout=5.0)
                        if self._action_thread.is_alive():
                            logging.warning("Action thread did not stop gracefully within timeout.")
                    
                    logging.debug("Action thread stopped. Waiting for next start signal...")
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
            # Clean up: stop action thread if still running
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
        Wrapper for running action() method in a loop until stopped.
        Runs in a separate thread.
        """
        try:
            while self.running.get():
                if self.options.allowed_states:
                    # Ensure still in allowed states
                    current_state = self.req.getParameter(self.options.state_param).get().value[0]
                    if current_state not in [s.value for s in self.options.allowed_states]:
                        logging.warning("System no longer in allowed states. Stopping action.")
                        self.running.set(False)
                        break
                self.action()
        except StopSignal:
            logging.info("Action thread received stop signal.")
        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Error in action thread: {e}\nTraceback:\n{tb}")
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

    options = McxClientAppOptions.from_json('config.json')

    logging.info(f"McxClientAppOptions initialized: {options.as_dict()}")
    app = ExampleApp(options)
    app.run()
