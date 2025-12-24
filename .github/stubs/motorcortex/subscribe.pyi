from motorcortex.request import ConnectionState as ConnectionState, Reply as Reply, Request as Request
from motorcortex.setup_logger import logger as logger
from motorcortex.state_callback_handler import StateCallbackHandler as StateCallbackHandler
from motorcortex.subscription import Subscription as Subscription

class Subscribe:
    """Subscribe class is used to receive continuous parameter updates from the motorcortex server.

        Subscribe class simplifies creating and removing subscription groups.

        Args:
            req(Request): reference to a Request instance
            protobuf_types(MessageTypes): reference to a MessageTypes instance

    """
    def __init__(self, req, protobuf_types) -> None: ...
    def connect(self, url, **kwargs):
        """Open a subscription connection.

            Args:
                url(str): motorcortex server URL

            Returns:
                bool: True - if connected, False otherwise
        """
    def close(self) -> None:
        """Close connection to the server"""
    def run(self, socket) -> None: ...
    def subscribe(self, param_list, group_alias, frq_divider: int = 1):
        """Create a subscription group for a list of the parameters.

            Args:
                param_list(list(str)): list of the parameters to subscribe to
                group_alias(str): name of the group
                frq_divider(int): frequency divider is a downscaling factor for the group publish rate

            Returns:
                  Subscription: A subscription handle, which acts as a JavaScript Promise,
                  it is resolved when the subscription is ready or failed. After the subscription
                  is ready, the handle is used to retrieve the latest data.
        """
    def unsubscribe(self, subscription):
        """Unsubscribe from the group.

            Args:
                subscription(Subscription): subscription handle

            Returns:
                  Reply: Returns a Promise, which resolves when the unsubscribe
                  operation is complete, fails otherwise.

        """
    def connectionState(self): ...
    def resubscribe(self) -> None: ...
