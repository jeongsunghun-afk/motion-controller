"""Simple watchdog helper for MCX client apps.

This module provides a small helper class to toggle a heartbeat and control
watchdog flags in the Motorcortex parameter tree. Typical parameter paths
expected under the configured `watchdog_folder_path` are:

- `.../disable` (bool) - disable the watchdog
- `.../on_input_change` (bool) - enable/disable heartbeat on input change
- `.../input` (bool) - heartbeat toggle written by `iterate()`

The class is intentionally thin: network interactions are proxied through a
`motorcortex.Request` instance set via `set_request()`.
"""

import motorcortex
from typing import Optional as TypingOptional, Any
import logging


class McxWatchdog:
    """Watchdog helper that updates a heartbeat parameter in Motorcortex.

    Args:
        watchdog_folder_path: Base parameter path for watchdog parameters.
        req: Optional Motorcortex Request object. Can be injected later
            with :meth:`set_request`.
        enabled: Whether the watchdog is enabled. When False, calls are no-ops.

    Attributes:
        watchdog_folder_path: The base path for watchdog parameters.
    """

    def __init__(self, watchdog_folder_path: str, req:TypingOptional[motorcortex.Request]=None, enabled:bool=True) -> None:
        self.watchdog_folder_path: str = watchdog_folder_path
        self.__req: TypingOptional[motorcortex.Request] = req
        self.__heartbeat: bool = False
        self.__enabled: bool = enabled

    def set_request(self, req: motorcortex.Request) -> None:
        """Set or replace the motorcortex Request used by the watchdog.

        Args:
            req: A connected `motorcortex.Request` instance.
        """
        self.__req = req

    def _set_watchdog_param(self, name: str, value: Any) -> bool:
        """Internal helper to set a watchdog parameter with null-safety.

        Args:
            name: Parameter name relative to `watchdog_folder_path`.
            value: Value to write.

        Returns:
            True on success, False on failure or if watchdog is disabled / request not set.
        """
        if not self.__enabled:
            logging.debug("Watchdog is disabled; skipping _set_watchdog_param(%s)", name)
            return False

        if self.__req is None:
            logging.error("No Request object set for watchdog; cannot set %s", name)
            return False

        full_path = f"{self.watchdog_folder_path}/{name}"
        try:
            result: TypingOptional[motorcortex.motorcortex_pb2.StatusMsg] = self.__req.setParameter(full_path, value).get()
        except Exception as exc:  # pragma: no cover - defensive
            logging.exception("Exception while setting watchdog param %s: %s", full_path, exc)
            return False

        if result is not None and getattr(result, 'status', None) == motorcortex.OK:
            logging.debug("Watchdog param %s set to %s", full_path, value)
            return True

        logging.error("Failed to set watchdog param %s to %s: %s", full_path, value, result)
        return False
    
    def setEnable(self, value: bool)->bool:
        """
        Enables or disables the watchdog.
        Args:
            value (bool): If True, enables the watchdog; if False, disables it.
        Returns:
            bool: The new enabled state.
        """

        self.__enabled = value

    def setDisable(self, value: bool) -> bool:
        """Enable or disable the watchdog via the `disable` parameter.

        Args:
            value: True to disable the watchdog, False to enable it.

        Returns:
            True if the operation succeeded, False otherwise.
        """
        return self._set_watchdog_param('disable', value)

    def setOnInputChange(self, value: bool) -> bool:
        """Set whether the watchdog heartbeat should toggle on input changes.

        Args:
            value: True to enable heartbeat on input change, False to disable.

        Returns:
            True if the operation succeeded, False otherwise.
        """
        return self._set_watchdog_param('on_input_change', value)

    def iterate(self) -> bool:
        """Toggle the heartbeat parameter to indicate liveness.

        This method simply flips an internal boolean and writes it to
        `<watchdog_folder_path>/input`. It performs null-safety checks and
        returns a boolean success indicator rather than raising.

        Returns:
            True if the heartbeat was written successfully, False otherwise.
        """
        if not self.__enabled:
            logging.debug("Watchdog iterate() called while disabled")
            return False

        if self.__req is None:
            logging.error("No Request object set for watchdog; cannot update heartbeat")
            return False

        self.__heartbeat = not self.__heartbeat
        return self._set_watchdog_param('input', self.__heartbeat)