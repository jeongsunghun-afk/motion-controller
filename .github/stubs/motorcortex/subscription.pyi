from _typeshed import Incomplete
from typing import Any, Callable, NamedTuple

class Timespec:
    """
    Represents a timestamp with seconds and nanoseconds.

    Provides conversion properties for seconds, milliseconds, microseconds, and nanoseconds.
    Prefer using this class for new code instead of standalone functions.
    """
    def __init__(self, sec: int, nsec: int) -> None: ...
    def __eq__(self, other: object) -> bool:
        """
        Compare two Timespec objects for equality.

        Args:
            other (object): Another Timespec instance.

        Returns:
            bool: True if both timestamps are equal, False otherwise.
        """
    def __lt__(self, other: Timespec) -> bool: ...
    def __le__(self, other: Timespec) -> bool: ...
    def __add__(self, other: Timespec) -> Timespec: ...
    @staticmethod
    def from_msec(msec: float) -> Timespec: ...
    @property
    def sec(self) -> float:
        """
        Returns the timestamp as seconds (float).
        """
    @property
    def msec(self) -> float:
        """
        Returns the timestamp as milliseconds (float).
        """
    @property
    def usec(self) -> float:
        """
        Returns the timestamp as microseconds (float).
        """
    @property
    def nsec(self) -> int:
        """
        Returns the timestamp as nanoseconds (int).
        """
    def to_tuple(self) -> tuple[int, int]: ...

class Parameter(NamedTuple):
    timestamp: Incomplete
    value: Incomplete

def compare_timespec(timestamp1: Timespec, timestamp2: Timespec) -> bool:
    """
    Compare two timestamps.

    Args:
        timestamp1 (timespec): First timestamp to compare.
        timestamp2 (timespec): Second timestamp to compare.

    Returns:
        bool: True if both timestamps are equal, False otherwise.

    Note:
        For new code, use Timespec.__eq__ instead.
    """
def timespec_to_sec(timestamp: Timespec) -> float:
    """
    Convert a timestamp to seconds.

    Args:
        timestamp (timespec): Timestamp to convert.

    Returns:
        float: Time in seconds.

    Note:
        For new code, use Timespec.sec_value instead.
    """
def timespec_to_msec(timestamp: Timespec) -> float:
    """
    Convert a timestamp to milliseconds.

    Args:
        timestamp (timespec): Timestamp to convert.

    Returns:
        float: Time in milliseconds.

    Note:
        For new code, use Timespec.msec instead.
    """
def timespec_to_usec(timestamp: Timespec) -> float:
    """
    Convert a timestamp to microseconds.

    Args:
        timestamp (timespec): Timestamp to convert.

    Returns:
        float: Time in microseconds.

    Note:
        For new code, use Timespec.usec instead.
    """
def timespec_to_nsec(timestamp: Timespec) -> int:
    """
    Convert a timestamp to nanoseconds.

    Args:
        timestamp (timespec): Timestamp to convert.

    Returns:
        int: Time in nanoseconds.

    Note:
        For new code, use Timespec.nsec_value instead.
    """

class Subscription:
    '''
    Represents a subscription to a group of parameters in Motorcortex.

    The Subscription class allows you to:
    - Access the latest values and timestamps for a group of parameters.
    - Poll for updates or use observer callbacks for real-time notifications.
    - Chain asynchronous operations using `then` and `catch` (promise-like interface).

    Attributes:
        group_alias (str): Alias for the parameter group.
        protobuf_types (Any): Protobuf type definitions.
        frq_divider (str): Frequency divider for the group.
        pool (Any): Thread or process pool for observer callbacks.

    Methods:
        id() -> int
            Returns the subscription identifier.

        alias() -> str
            Returns the group alias.

        frqDivider() -> str
            Returns the frequency divider of the group.

        read() -> Optional[List[Parameter]]
            Returns the latest values of the parameters in the group.

        layout() -> Optional[List[str]]
            Returns the ordered list of parameter paths in the group.

        done() -> bool
            Returns True if the subscription is finished or cancelled.

        get(timeout_sec: float = 1.0) -> Optional[Any]
            Waits for the subscription to complete, returns the result or None on timeout.

        then(subscribed_clb: Callable[[Any], None]) -> Subscription
            Registers a callback for successful subscription completion.

        catch(failed: Callable[[], None]) -> Subscription
            Registers a callback for subscription failure.

        notify(observer_list: Union[Callable, List[Callable]]) -> None
            Registers observer(s) to be notified on every group update.

    Examples:
        >>> # Make sure you have a valid connection
        >>> subscription = sub.subscribe(paths, "group1", 100)
        >>> result = subscription.get()
        >>> if result is not None and result.status == motorcortex.OK:
        ...     print(f"Subscription successful, layout: {subscription.layout()}")
        ... else:
        ...     print(f"Subscription failed. Check parameter paths: {paths}")
        ...     sub.close()
        ...     exit()
        >>> # Use promise-like interface
        >>> subscription.then(lambda res: print("Subscribed:", res)).catch(lambda: print("Failed"))
        >>> # Use observer for real-time updates
        >>> def on_update(parameters):
        ...     for param in parameters:
        ...         timestamp = param.timestamp.sec + param.timestamp.nsec * 1e-9
        ...         print(f"Update: {timestamp:.6f}, {param.value}")
        >>> subscription.notify(on_update)
        >>> print("Waiting for parameter updates...")
        >>> import time
        >>> while True:
        ...     time.sleep(1)
    '''
    def __init__(self, group_alias: str, protobuf_types: Any, frq_divider: str, pool: Any) -> None: ...
    def id(self) -> int:
        """
            Returns:
                int: subscription identifier
        """
    def alias(self) -> str:
        """
            Returns:
                str: group alias
        """
    def frqDivider(self) -> str:
        """
            Returns:
                str: frequency divider of the group
        """
    def read(self) -> list['Parameter'] | None:
        """Read the latest values of the parameters in the group.

            Returns:
                list(Parameter): list of parameters
        """
    def layout(self) -> list[str] | None:
        """Get a layout of the group.

            Returns:
                list(str): ordered list of the parameters in the group
        """
    def done(self) -> bool:
        '''
            Returns:
                bool: True if the call was successfully canceled or finished running.

            Examples:
                >>> subscription = sub.subscribe("root/logger/logOut", "log")
                >>> while not subscription.done():
                >>>     time.sleep(0.1)
        '''
    def get(self, timeout_sec: float = 1.0) -> Any | None:
        '''
            Returns:
                bool: StatusMsg if the call was successful, None if timeout happened.

            Examples:
                >>> subscription = sub.subscribe("root/logger/logOut", "log")
                >>> done = subscription.get()
        '''
    def then(self, subscribed_clb: Callable[[Any], None]) -> Subscription:
        '''JavaScript-like promise, which is resolved when the subscription is completed.

            Args:
                subscribed_clb: callback which is resolved when the subscription is completed.

            Returns:
                self pointer to add \'catch\' callback

            Examples:
                >>> subscription = sub.subscribe("root/logger/logOut", "log")
                >>> subscription.then(lambda val: print("got: %s"%val)).catch(lambda d: print("failed"))
        '''
    def catch(self, failed: Callable[[], None]) -> Subscription:
        '''JavaScript-like promise, which is resolved when subscription has failed.

            Args:
                failed: callback which is resolved when the subscription has failed

            Returns:
                self pointer to add \'then\' callback

            Examples:
                >>> subscription = sub.subscribe("root/logger/logOut", "log")
                >>> subscription.catch(lambda d: print("failed")).then(lambda val: print("got: %s"%val))
        '''
    def notify(self, observer_list: Callable[[list['Parameter']], None] | list[Callable[[list['Parameter']], None]]) -> None:
        """Set an observer, which is notified on every group update.

            Args:
                observer_list: a callback function (or list of callback functions)
                to notify when new values are available

            Examples:
                  >>> def update(parameters):
                  >>>   print(parameters) #list of Parameter tuples
                  >>> ...
                  >>> data_sub.notify(update)

        """
