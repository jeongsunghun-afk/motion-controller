from _typeshed import Incomplete
from motorcortex.setup_logger import logger as logger

class StateCallbackHandler:
    """Handles state change callbacks processing"""
    running: bool
    callback_queue: Incomplete
    callback_thread: Incomplete
    state_update_handler: Incomplete
    def __init__(self) -> None: ...
    def start(self, state_update_handler) -> None:
        """Start the callback handler with the given update function"""
    def stop(self) -> None:
        """Stop the callback handler and clean up"""
    def notify(self, *args) -> None:
        """Queue a state update notification"""
