import motorcortex
from _typeshed import Incomplete
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar('T')
waitForOperators: Incomplete
stateCommand: Incomplete
state: Incomplete

class StopSignal(Exception):
    """
    Exception raised when a stop signal is received from the Motorcortex server.
    """

@dataclass
class McxClientAppOptions:
    '''
    Configuration options for McxClientApp.

    Attributes:
        login (str): Username for authenticating with the Motorcortex server.
        password (str): Password for authenticating with the Motorcortex server.
        target_url (str): WebSocket URL of the Motorcortex server (e.g., \'wss://localhost\').
            This is the endpoint used to establish the connection.
        cert (str): Path to the SSL certificate file for secure connection (e.g., \'mcx.cert.crt\').
            Required for encrypted communication with the server. This is the fallback if "/etc/ssl/certs/mcx.cert.pem" is not found.
        statecmd_param (str): Parameter path for sending state commands to the server (default: \'root/Logic/stateCommand\').
            Used to control the robot or system state.
        state_param (str): Parameter path for reading the current state from the server (default: \'root/Logic/state\').
            Used to monitor the robot or system state.
        start_stop_param (str|None): Optional parameter path for start/stop control (default: None).
            If provided, the application will monitor this parameter to start or stop operations.
    '''
    login: str
    password: str
    target_url: str = ...
    cert: str = ...
    statecmd_param: str = ...
    state_param: str = ...
    start_stop_param: str | None = ...

class ThreadSafeValue(Generic[T]):
    """
    Thread-safe single-value container with optional blocking read.
    """
    def __init__(self, initial_value: T | None = None) -> None: ...
    def get(self) -> T | None:
        """
        Get the current value in a thread-safe manner.

        Returns:
            The current value.
        """
    def set(self, value: T) -> None:
        """
        Set a new value in a thread-safe manner.

        Args:
            value: The new value to set.
        """

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
    options: Incomplete
    parameter_tree: motorcortex.ParameterTree
    motorcortex_types: motorcortex.MessageTypes
    req: motorcortex.Request | None
    sub: motorcortex.Subscription | None
    running: ThreadSafeValue
    def __init__(self, options: McxClientAppOptions | None = None) -> None:
        """
        Initialize the MCxClientApp.

        Args:
            options (McxClientAppOptions): Optional McxClientAppOptions dataclass with configuration.
        """
    def connect(self) -> None:
        """
        Establish a connection to the Motorcortex server and set up subscriptions.
        Raises:
            Exception: If connection fails.
        """
    def wait_for(self, param: str, value: object = True, index: int = 0, timeout: float = 30, testinterval: float = 0.2, operat: str = '==', block_stop_signal: bool = False) -> bool:
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
    def wait(self, timeout: float = 30, testinterval: float = 0.2, block_stop_signal: bool = False) -> bool:
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
    def reset(self) -> None:
        """
        Reset the running flag to False.
        """
    def engage(self) -> None:
        """
        Command the system to the ENGAGED state and wait until it is engaged.
        Sends the command every 5 seconds until engaged or stopped.
        """
    def disengage(self) -> None:
        """
        Command the system to the OFF state and wait until it is off.
        Sends the command every 5 seconds until off or stopped.
        """
    def action(self) -> None:
        """
        Main action loop called repeatedly while the system is running.
        Override this method in your subclass to implement custom behavior.
        
        In the base class, this method runs in the main thread.
        Use wait() or wait_for() methods which will raise StopSignal when stopped.
        """
    def startOp(self) -> None:
        """
        Called after connection is established, before engaging the system.
        Override this method to set parameters or perform initialization.
        """
    def onExit(self) -> None:
        """
        Called before disconnecting from the server.
        Override this method to perform cleanup operations.
        """
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
    def __init__(self, options: McxClientAppOptions | None = None) -> None:
        """
        Initialize the McxClientAppThread.

        Args:
            options (McxClientAppOptions): Optional McxClientAppOptions dataclass with configuration.
        """
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
