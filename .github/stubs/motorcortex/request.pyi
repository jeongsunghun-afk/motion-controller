from concurrent.futures import Future as Future
from enum import Enum
from motorcortex.message_types import MessageTypes as MessageTypes
from motorcortex.parameter_tree import ParameterTree as ParameterTree
from motorcortex.reply import Reply as Reply
from motorcortex.setup_logger import logger as logger
from motorcortex.state_callback_handler import StateCallbackHandler as StateCallbackHandler
from threading import Event
from typing import Any, Callable

class ConnectionState(Enum):
    """Enumeration of connection states.
    
        - CONNECTING:           Connection is being established.
        - CONNECTION_OK:        Connection is successfully established.
        - CONNECTION_LOST:      Connection was lost.
        - CONNECTION_FAILED:    Connection attempt failed.
        - DISCONNECTING:        Connection is being closed.
        - DISCONNECTED:         Connection is closed.
    """
    CONNECTING = 0
    CONNECTION_OK = 1
    CONNECTION_LOST = 2
    CONNECTION_FAILED = 3
    DISCONNECTING = 4
    DISCONNECTED = 5

class Request:
    '''
    Represents a request connection to a Motorcortex server.

    The Request class allows you to:
    - Establish and manage a connection to a Motorcortex server.
    - Perform login authentication.
    - Retrieve, set, and overwrite parameter values.
    - Manage parameter groups for efficient batch operations.
    - Save and load parameter trees.
    - Chain asynchronous operations using a promise-like interface (`Reply`).

    Methods:
        url() -> Optional[str]
            Returns the current connection URL.

        connect(url: str, **kwargs) -> Reply
            Establishes a connection to the server.

        close() -> None
            Closes the connection and cleans up resources.

        send(encoded_msg: Any, do_not_decode_reply: bool = False) -> Optional[Reply]
            Sends an encoded message to the server.

        login(login: str, password: str) -> Reply
            Sends a login request.

        connectionState() -> ConnectionState
            Returns the current connection state.

        getParameterTreeHash() -> Reply
            Requests the parameter tree hash from the server.

        getParameterTree() -> Reply
            Requests the parameter tree from the server.

        save(path: str, file_name: str) -> Reply
            Requests the server to save the parameter tree to a file.

        setParameter(path: str, value: Any, type_name: Optional[str] = None, offset: int = 0, length: int = 0) -> Reply
            Sets a new value for a parameter.

        setParameterList(param_list: List[dict]) -> Reply
            Sets new values for a list of parameters.

        getParameter(path: str) -> Reply
            Requests a parameter value and description.

        getParameterList(path_list: List[str]) -> Reply
            Requests values and descriptions for a list of parameters.

        overwriteParameter(path: str, value: Any, force_activate: bool = False, type_name: Optional[str] = None) -> Reply
            Overwrites a parameter value and optionally forces it to stay active.

        releaseParameter(path: str) -> Reply
            Releases the overwrite operation for a parameter.

        createGroup(path_list: List[str], group_alias: str, frq_divider: int = 1) -> Reply
            Creates a subscription group for a list of parameters.

        removeGroup(group_alias: str) -> Reply
            Unsubscribes from a group.

    Examples:
        >>> # Establish a connection
        >>> req = motorcortex.Request(protobuf_types, parameter_tree)
        >>> reply = req.connect("tls+tcp://localhost:6501", certificate="path/to/ca.crt")
        >>> if reply.get():
        ...     print("Connected!")
        >>> # Login
        >>> login_reply = req.login("user", "password")
        >>> if login_reply.get().status == motorcortex.OK:
        ...     print("Login successful")
        >>> # Get a parameter
        >>> param_reply = req.getParameter("MyDevice.MyParam")
        >>> param = param_reply.get()
        >>> print("Value:", param.value)
        >>> # Set a parameter
        >>> req.setParameter("MyDevice.MyParam", 42)
        >>> # Clean up
        >>> req.close()
    '''
    def __init__(self, protobuf_types: MessageTypes, parameter_tree: ParameterTree) -> None:
        """
        Initialize a Request object.

        Args:
            protobuf_types: Motorcortex message types module.
            parameter_tree: ParameterTree instance.
        """
    def url(self) -> str | None:
        """Return the current connection URL."""
    def connect(self, url: str, **kwargs) -> Reply:
        """
        Establish a connection to the Motorcortex server.

        Args:
            url: Connection URL.
            **kwargs: Additional connection parameters.

        Returns:
            Reply: A promise that resolves when the connection is established.
        """
    def close(self) -> None:
        """
        Close the request connection and clean up resources.
        """
    def send(self, encoded_msg: Any, do_not_decode_reply: bool = False) -> Reply | None:
        """
        Send an encoded message to the server.

        Args:
            encoded_msg: Encoded protobuf message.
            do_not_decode_reply: If True, do not decode the reply.

        Returns:
            Reply or None: A promise for the reply, or None if not connected.
        """
    def login(self, login: str, password: str) -> Reply:
        """
        Send a login request to the server.

        Args:
            login: User login.
            password: User password.

        Returns:
            Reply: A promise for the login reply.
        """
    def connectionState(self) -> ConnectionState:
        """
        Get the current connection state.

        Returns:
            ConnectionState: The current state.
        """
    def getParameterTreeHash(self) -> Reply:
        """
        Request a parameter tree hash from the server.

        Returns:
            Reply: A promise for the parameter tree hash.
        """
    def getParameterTree(self) -> Reply:
        """
        Request a parameter tree from the server.

        Returns:
            Reply: A promise for the parameter tree.
        """
    def save(self, path: str, file_name: str) -> Reply:
        """
        Request the server to save a parameter tree to a file.

        Args:
            path: Path to save the file.
            file_name: Name of the file.

        Returns:
            Reply: A promise for the save operation.
        """
    def setParameter(self, path: str, value: Any, type_name: str | None = None, offset: int = 0, length: int = 0) -> Reply:
        """
        Set a new value for a parameter.

        Args:
            path: Parameter path.
            value: New value.
            type_name: Type name (optional).
            offset: Offset in array (optional).
            length: Number of elements to update (optional).

        Returns:
            Reply: A promise for the set operation.
        """
    def setParameterList(self, param_list: list[dict]) -> Reply:
        """
        Set new values for a list of parameters.

        Args:
            param_list: List of parameter dicts with 'path' and 'value'.

        Returns:
            Reply: A promise for the set operation.
        """
    def getParameter(self, path: str) -> Reply:
        """
        Request a parameter value and description from the server.

        Args:
            path: Parameter path.

        Returns:
            Reply: A promise for the parameter value.
        """
    def getParameterList(self, path_list: list[str]) -> Reply:
        """
        Request values and descriptions for a list of parameters.

        Args:
            path_list: List of parameter paths.

        Returns:
            Reply: A promise for the parameter list.
        """
    def overwriteParameter(self, path: str, value: Any, force_activate: bool = False, type_name: str | None = None) -> Reply:
        """
        Overwrite a parameter value and optionally force it to stay active.

        Args:
            path: Parameter path.
            value: New value.
            force_activate: Force value to stay active.
            type_name: Type name (optional).

        Returns:
            Reply: A promise for the overwrite operation.
        """
    def releaseParameter(self, path: str) -> Reply:
        """
        Release the overwrite operation for a parameter.

        Args:
            path: Parameter path.

        Returns:
            Reply: A promise for the release operation.
        """
    def createGroup(self, path_list: list[str], group_alias: str, frq_divider: int = 1) -> Reply:
        """
        Create a subscription group for a list of parameters.

        Args:
            path_list: List of parameter paths.
            group_alias: Group alias.
            frq_divider: Frequency divider.

        Returns:
            Reply: A promise for the group creation.
        """
    def removeGroup(self, group_alias: str) -> Reply:
        """
        Unsubscribe from a group.

        Args:
            group_alias: Group alias.

        Returns:
            Reply: A promise for the unsubscribe operation.
        """
    @staticmethod
    def parse(conn_timeout_ms: int = 0, timeout_ms: int | None = None, recv_timeout_ms: int | None = None, certificate: str | None = None, login: str | None = None, password: str | None = None, state_update: Callable | None = None) -> tuple[int, int | None, str | None, Callable | None]:
        """
        Parses connection parameters for the connect method.

        Args:
            conn_timeout_ms: Connection timeout in milliseconds.
            timeout_ms: Alternative timeout in milliseconds.
            recv_timeout_ms: Receive timeout in milliseconds.
            certificate: Path to the TLS certificate.
            login: Optional login name.
            password: Optional password.
            state_update: Optional state update callback.

        Returns:
            Tuple of (conn_timeout_ms, recv_timeout_ms, certificate, state_update).
        """
    @staticmethod
    def waitForConnection(event: Event, timeout_sec: float, is_connected_fn: Callable[[], bool] | None = None) -> bool:
        """
        Waits for the connection event or times out.

        Args:
            event: Event to wait on.
            timeout_sec: Timeout in seconds.
            is_connected_fn: Optional function to check connection status.

        Returns:
            True if connection is established, raises on failure or timeout.
        """
    @staticmethod
    def saveParameterTreeFile(path: str, parameter_tree: ParameterTree) -> ParameterTree:
        """
        Saves the parameter tree to a file in the cache.

        Args:
            path: File path to save the parameter tree.
            parameter_tree: ParameterTree instance.

        Returns:
            The saved ParameterTree instance.
        """
    @staticmethod
    def loadParameterTreeFile(path: str, protobuf_types: MessageTypes) -> ParameterTree | None:
        """
        Loads the parameter tree from a cached file if available and valid.

        Args:
            path: File path to load the parameter tree from.
            protobuf_types: Protobuf type definitions.

        Returns:
            The loaded ParameterTree instance, or None if not found/invalid.
        """
