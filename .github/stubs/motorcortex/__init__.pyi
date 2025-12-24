from motorcortex.message_types import MessageTypes as MessageTypes
from motorcortex.parameter_tree import ParameterTree as ParameterTree
from motorcortex.reply import Reply as Reply
from motorcortex.request import ConnectionState as ConnectionState, Request as Request
from motorcortex.setup_logger import logger as logger
from motorcortex.state_callback_handler import StateCallbackHandler as StateCallbackHandler
from motorcortex.subscribe import Subscribe as Subscribe
from motorcortex.subscription import Subscription as Subscription
from motorcortex.version import __version__ as __version__

def parseUrl(url: str) -> tuple[str, str, int | None, int | None]:
    """
    Parses a Motorcortex connection URL to extract request and subscribe addresses and ports.

    Args:
        url (str): The connection URL, expected in the format 'address:req_port:sub_port'.

    Returns:
        tuple: (req_address, sub_address, req_port, sub_port)
            - req_address (str): Address for request connection.
            - sub_address (str): Address for subscribe connection.
            - req_port (int or None): Port for request connection.
            - sub_port (int or None): Port for subscribe connection.

    If the URL does not contain ports, default endpoints '/mcx_req' and '/mcx_sub' are appended.
    """
def makeUrl(address: str, port: int | None) -> str:
    """
    Constructs a URL string from an address and port.

    Args:
        address (str): The base address.
        port (int or None): The port number.

    Returns:
        str: The combined address and port in the format 'address:port', or just 'address' if port is None.
    """
def connect(url: str, motorcortex_types: object, param_tree: ParameterTree, reconnect: bool = True, **kwargs) -> tuple['Request', 'Subscribe']:
    '''
    Establishes connections to Motorcortex request and subscribe endpoints, performs login, and loads the parameter tree.

    Args:
        url (str): Connection URL in the format \'address:req_port:sub_port\'.
        motorcortex_types (module): Motorcortex message types module.
        param_tree (ParameterTree): ParameterTree instance to load parameters into.
        reconnect (bool, optional): Whether to enable automatic reconnection. Defaults to True.
        **kwargs: Additional keyword arguments, including \'login\' and \'password\' for authentication.

    Returns:
        tuple: (req, sub)
            - req (Request): Established request connection.
            - sub (Subscribe): Established subscribe connection.

    Raises:
        RuntimeError: If connection or login fails.

    Examples:
        >>> from motorcortex import connect, MessageTypes, ParameterTree
        >>> url = "127.0.0.1:5555:5556"
        >>> types = MessageTypes()
        >>> tree = ParameterTree()
        >>> req, sub = connect(url, types, tree, certificate="mcx.cert.crt", timeout_ms=1000, login="admin", password="iddqd")
        >>> print(tree)  # Parameter tree loaded from server
    '''
def statusToStr(motorcortex_msg: object, code: int) -> str:
    '''Converts status codes to a readable message.

        Args:
            motorcortex_msg(Module): reference to a motorcortex module
            code(int): status code

        Returns:
            str: status message

        Examples:
            >>> login_reply = req.login("admin", "iddqd")
            >>> login_reply_msg = login_reply.get()
            >>> if login_reply_msg.status != motorcortex_msg.OK:
            >>>     print(motorcortex.statusToStr(motorcortex_msg, login_reply_msg.status))

    '''
