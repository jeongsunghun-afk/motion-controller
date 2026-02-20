import motorcortex
from typing import Any, Optional as TypingOptional, Callable
from enum import IntEnum
import logging
import traceback

class MotorcortexErrorLevel(IntEnum):
    """
    Motorcortex error severity levels corresponding to the C typedef motorcortex_ErrorLevel.

    Members:
        ERROR_LEVEL_UNDEFINED (0): Undefined error level.
        INFO (1): Information message.
        WARNING (2): Warning message.
        FORCED_DISENGAGE (3): Graceful software stop, caused by a hardware malfunction or wrong user actions.
        SHUTDOWN (4): More abrupt software stop, caused by a hardware malfunction.
        EMERGENCY_STOP (5): Abrupt software and hardware stop, caused by a hardware malfunction.
    """
    ERROR_LEVEL_UNDEFINED = 0
    INFO = 1
    WARNING = 2
    FORCED_DISENGAGE = 3
    SHUTDOWN = 4
    EMERGENCY_STOP = 5

class McxErrorHandler():
    """
    Custom error handler for Motorcortex client applications.
    """
    def __init__(self, error_folder_path: str, error_reset_parameter: str, req:TypingOptional[motorcortex.Request]=None, sub: TypingOptional[motorcortex.Subscription]=None,
                 acknowledge_callback: TypingOptional[Callable] = None, subsystem_id: TypingOptional[int]=None,
                 enabled:bool=True)-> None:
        self.error_folder_path: str = error_folder_path
        self.error_reset_parameter: str = error_reset_parameter
        self.__req: TypingOptional[motorcortex.Request] = req
        self.__sub: TypingOptional[motorcortex.Subscription] = sub
        self.__acknowledge_callback: TypingOptional[Callable] = acknowledge_callback
        self.subsystem_id: TypingOptional[int] = subsystem_id
        self.__ack_subscription: TypingOptional[motorcortex.Subscribe] = None

        self.enabled = enabled

        self.__last_ack_value: int = 0

    def set_enabled(self, enable:bool)-> None:
        """
        Enable or disable the error handler.

        Args:
            enable (bool): True to enable, False to disable.
        """
        self.enabled = enable

    def set_acknowledge_callback(self, callback:Callable)-> None:
        """
        Set the acknowledge callback function.

        Args:
            callback (function): The callback function to be called on acknowledgment.
        """
        self.__acknowledge_callback = callback

    def set_request(self, req:motorcortex.Request)-> None:
        """
        Set the Motorcortex request object.

        Args:
            req (motorcortex.Request): The Motorcortex request object.
        """
        self.__req = req

    def set_subscription(self, sub:motorcortex.Subscription)-> None:
        """
        Set the Motorcortex subscription object.

        Args:
            sub (motorcortex.Subscription): The Motorcortex subscription object.
        """
        self.__sub = sub

    def set_request_and_subscription(self, req:motorcortex.Request, sub:motorcortex.Subscription)-> None:
        """
        Set both the Motorcortex request and subscription objects.

        Args:
            req (motorcortex.Request): The Motorcortex request object.
            sub (motorcortex.Subscription): The Motorcortex subscription object.
        """
        self.__req = req
        self.__sub = sub

    def set_subsystem_id(self, subsystem_id:int)-> None:
        """
        Set the subsystem ID for error handling.

        Args:
            subsystem_id (int): The subsystem ID.
        """
        self.subsystem_id = subsystem_id
        
    def start_subscription(self) -> None:
        """
        Start subscription to acknowledge error.
        """
        if self.enabled is False:
            logging.debug("Error handler is disabled; not starting acknowledgment subscription.")
            return
        if self.__sub is not None:
            try:
                print(f"Subscribing to acknowledge parameter: {self.error_reset_parameter}")
                self.__ack_subscription = self.__sub.subscribe(
                    [self.error_reset_parameter],
                    group_alias=f"error_ack_{self.subsystem_id or '0'}",
                    frq_divider=10
                )
                result = self.__ack_subscription.get()
                if result is not None and result.status == motorcortex.OK:
                    logging.debug(f"Error acknowledge subscription successful: {self.error_reset_parameter}")
                    self.__ack_subscription.notify(self._on_acknowledge)
                else:
                    logging.error("Failed to subscribe to error acknowledge parameter.")
            except Exception as e:
                tb = traceback.format_exc()
                logging.error(f"Exception while subscribing to acknowledge parameter: {e}\nTraceback:\n{tb}")
                raise

    def _on_acknowledge(self, data) -> None:
        try:
            value = int(data[0].value[0])
            prev = self.__last_ack_value

            # Trigger only on rising edge: 0 -> 1
            if prev == 0 and value == 1:
                logging.info("Error acknowledged (rising edge).")
                if self.__acknowledge_callback is not None:
                    self.__acknowledge_callback()
                self.trigger_error(MotorcortexErrorLevel.ERROR_LEVEL_UNDEFINED, 0, self.subsystem_id)

            # Update last value
            self.__last_ack_value = value

        except Exception as e:
            tb = traceback.format_exc()
            logging.error(f"Exception in acknowledge callback: {e}\nTraceback:\n{tb}")
            return

    def trigger_error(self, level: MotorcortexErrorLevel, code: int, subsystem_id: TypingOptional[int]=None)-> None:
        """
        Trigger an error with the specified level and code.

        Args:
            level (MotorcortexErrorLevel): The severity level of the error.
            code (int): The error code.
            subsystem_id (int | None): The subsystem ID. If None, uses the instance's subsystem ID.
        """
        if self.enabled is False:
            logging.debug("Error handler is disabled; not triggering error.")
            return

        if subsystem_id is None:
            subsystem_id = self.subsystem_id
        if self.__req is not None:
            # Prepare parameter list: code, subsystem (if any), then trigger last
            param_list = [
                {"path": f"{self.error_folder_path}/serviceErrorCode", "value": code}
            ]
            if subsystem_id is not None:
                param_list.append({"path": f"{self.error_folder_path}/serviceErrorSubsystem", "value": subsystem_id})
            param_list.append({"path": f"{self.error_folder_path}/triggerErrorWithLevel", "value": level.value})

            results = self.__req.setParameterList(param_list).get()

            # Handle both list and single StatusMsg return
            if isinstance(results, list):
                # Results is a list of reply objects in the same order as param_list
                resultLevel = results[-1] if len(results) == len(param_list) else None
                resultCode = results[0] if len(results) >= 1 else None
                resultSubsystem = results[1] if subsystem_id is not None and len(results) > 2 else None
            else:
                # Only one parameter, results is a single StatusMsg
                resultLevel = results
                resultCode = results
                resultSubsystem = results if subsystem_id is not None else None

            if resultLevel is not None and getattr(resultLevel, 'status', None) == motorcortex.OK:
                logging.info(f"Triggered error level: {level.name} ({level.value})")
            else:
                logging.error(f"Failed to trigger error level: {level.name} ({level.value})")
            if resultCode is not None and getattr(resultCode, 'status', None) != motorcortex.OK:
                logging.error(f"Failed to set error code: {code}")
            if subsystem_id is not None:
                if resultSubsystem is not None and getattr(resultSubsystem, 'status', None) != motorcortex.OK:
                    logging.error(f"Failed to set error subsystem ID: {subsystem_id}")
        else:
            raise RuntimeError("Motorcortex Request object is not set. Cannot trigger error.")
        
    
    def trigger_info(self, code: int, subsystem_id: TypingOptional[int]=None)-> None:
        """
        Trigger an info message with the specified code.

        Args:
            code (int): The info code.
            subsystem_id (int | None): The subsystem ID. If None, uses the instance's subsystem ID.
        """
        self.trigger_error(MotorcortexErrorLevel.INFO, code, subsystem_id)
        
    def trigger_warning(self, code: int, subsystem_id: TypingOptional[int]=None)-> None:
        """
        Trigger a warning with the specified code.

        Args:
            code (int): The warning code.
            subsystem_id (int | None): The subsystem ID. If None, uses the instance's subsystem ID.
        """
        self.trigger_error(MotorcortexErrorLevel.WARNING, code, subsystem_id)

    def trigger_forced_disengage(self, code: int, subsystem_id: TypingOptional[int]=None)-> None:
        """
        Trigger a forced disengage with the specified code.

        Args:
            code (int): The forced disengage code.
            subsystem_id (int | None): The subsystem ID. If None, uses the instance's subsystem ID.
        """
        self.trigger_error(MotorcortexErrorLevel.FORCED_DISENGAGE, code, subsystem_id)

    def trigger_shutdown(self, code: int, subsystem_id: TypingOptional[int]=None)-> None:
        """
        Trigger a shutdown with the specified code.

        Args:
            code (int): The shutdown code.
            subsystem_id (int | None): The subsystem ID. If None, uses the instance's subsystem ID.
        """
        self.trigger_error(MotorcortexErrorLevel.SHUTDOWN, code, subsystem_id)

    def trigger_emergency_stop(self, code: int, subsystem_id: TypingOptional[int]=None)-> None:
        """
        Trigger an emergency stop with the specified code.

        Args:
            code (int): The emergency stop code.
            subsystem_id (int | None): The subsystem ID. If None, uses the instance's subsystem ID.
        """
        self.trigger_error(MotorcortexErrorLevel.EMERGENCY_STOP, code, subsystem_id)