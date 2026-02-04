#
#   Developer : Coen Smeets (Coen@vectioneer.com)
#   All rights reserved. Copyright (c) 2025 VECTIONEER.
#

from typing import Callable, Optional, Any
from motorcortex import Subscription
from .McxClientApp import ThreadSafeValue


class ChangeDetector:
    """
    Detects changes in a parameter value over time.
    """
    
    def __init__(self)-> None:
        """
        Initialize the ChangeDetector.
        """
        self.__old_value: ThreadSafeValue = ThreadSafeValue(None)
        self.__value: ThreadSafeValue = ThreadSafeValue(None)
        self._value_changed: ThreadSafeValue = ThreadSafeValue(False)
    
    def set_value(self, value)-> None:
        """
        Set a new value and check for changes.
        
        Args:
            value: The new value to set.
        """
        old_value = self.__value.get()
        if old_value != value:
            self._value_changed.set(True)
        self.__old_value.set(old_value)
        self.__value.set(value)
        
    def get_value(self) -> Any:
        """
        Get the current value of the parameter.
        
        Returns:
            The last seen parameter value.
        """
        return self.__value.get()

    def has_changed(self, keep: bool = False, trigger_on_zero: bool = True) -> bool:
        """
        Check if the value has changed since the last check.

        Args:
            keep (bool): If True, keeps the changed state until reset is called. Defaults to False.
            trigger_on_zero (bool): If True, changes to zero are considered valid changes. 
                If False, changes TO zero value are ignored. Defaults to True.
                (Only works with non-array values. Otherwise it checks the first element of the array.)
        
        Returns:
            bool: True if value changed (and met the trigger_on_zero condition), False otherwise.
        """
        changed = self._value_changed.get()

        if changed:
            val = self.__value.get()
            if not trigger_on_zero:
                # take first element for containers, else the value itself
                first = val[0] if isinstance(val, (list, tuple)) and len(val) > 0 else val
                if first == 0:
                    changed = False

        if not keep:
            self._value_changed.set(False)

        return changed
    
    def reset(self) -> None:
        """
        Reset the detector state.
        
        Useful when you want to clear any pending change detections.
        """
        self.__value.set(None)
        self.__old_value.set(None)
        self._value_changed.set(False)
