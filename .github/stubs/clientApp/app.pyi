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

class McxClientAppConfiguration:
    '''
    Configuration options for McxClientApp.

    Attributes:
        login (str): Username for authenticating with the Motorcortex server.
        password (str): Password for authenticating with the Motorcortex server.
        target_url (str): Local Development WebSocket URL of the Motorcortex server (e.g., 'wss://localhost').
            This is the endpoint used to establish the connection.
        target_url_deployed (str): Deployed WebSocket URL of the Motorcortex server (default: 'wss://localhost').
        cert (str): Local Development path to the SSL certificate file for secure connection (e.g., 'mcx.cert.crt').
        cert_deployed (str): Deployed path to the SSL certificate file (default: '/etc/ssl/certs/mcx.cert.pem').
        statecmd_param (str): Parameter path for sending state commands to the server (default: 'root/Logic/stateCommand').
        state_param (str): Parameter path for reading the current state from the server (default: 'root/Logic/state').
        run_during_states (list[State]|None): List of allowed states during which iterate() can run (default None).
        start_stop_param (str|None): Optional parameter path for start/stop control (default: None).
    '''
    def __init__(
        self,
        login: str | None = None,
        password: str | None = None,
        target_url: str = "wss://localhost",
        target_url_deployed: str = "wss://localhost",
        cert: str = "mcx.cert.crt",
        cert_deployed: str = "/etc/ssl/certs/mcx.cert.pem",
        statecmd_param: str | None = "root/Logic/stateCommand",
        state_param: str | None = "root/Logic/state",
        run_during_states: list = None,
        start_stop_param: str | None = None,
        **kwargs
    ) -> None: ...
    
    def set_config_paths(self, deployed_config: str | None, non_deployed_config: str | None) -> None:
        """
        Set the configuration file paths for deployed and non-deployed environments.
        
        Args:
            deployed_config (str | None): Path to the configuration file used when deployed.
            non_deployed_config (str | None): Path to the configuration file used when not deployed.
        """
    
    @property
    def has_config(self) -> bool: ...
    
    @property
    def is_deployed(self) -> bool: ...
    
    @property
    def certificate(self) -> str: ...
    
    @property
    def ip_address(self) -> str: ...
    
    @property
    def run_during_states(self) -> list: ...
    
    @property
    def allowed_states(self) -> list: ...

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
    
    This base class does NOT use a separate thread for the iterate() method.
    
    To use this class, inherit from it and override the following methods:
        - iterate(): Main iterate loop (called repeatedly while running)
        - startOp(): Called after connection is established (optional)
        - onExit(): Called before disconnecting (optional)
    """
    options: Incomplete
    parameter_tree: motorcortex.ParameterTree
    motorcortex_types: motorcortex.MessageTypes
    req: motorcortex.Request | None
    sub: motorcortex.Subscription | None
    running: ThreadSafeValue
    def __init__(self, options: McxClientAppConfiguration) -> None:
        """
        Initialize the MCxClientApp.

        Args:
            options (McxClientAppConfiguration): McxClientAppConfiguration instance with configuration.
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
    def iterate(self) -> None:
        """
        Main iterate loop called repeatedly while the system is running.
        Override this method in your subclass to implement custom behavior.
        
        In the base class, this method runs in the main thread.
        Use wait() or wait_for() methods which will raise StopSignal when stopped.
        """
    def startOp(self) -> None:
        """
        Called after connection is established.
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
    
    This class extends MCxClientApp and runs the iterate() method in a separate thread,
    allowing the main thread to monitor start/stop signals independently.
    
    To use this class, inherit from it and override the following methods:
        - iterate(): Main iterate loop (called repeatedly in a separate thread)
        - startOp(): Called after connection is established (optional)
        - onExit(): Called before disconnecting (optional)
    """
    def __init__(self, options: McxClientAppConfiguration) -> None:
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
