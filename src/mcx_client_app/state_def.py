from enum import Enum

class StateCommand(Enum):
    """Enum for state commands sent to the Motorcortex server."""
    DO_NOTHING_E = -1
    GOTO_OFF_E = 0
    GOTO_IDLE_E = 1
    GOTO_ENGAGED_E = 2
    GOTO_REFERENCING_E = 4
    FORCE_IDLE_E = 10
    EMERGENCY_STOP_E = 20
    SAVE_CONFIGURATION = 254
    ACKNOWLEDGE_ERROR = 255

    @classmethod
    def from_value(cls, value):
        """Convert int, str, or enum to StateCommand."""
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        if isinstance(value, str):
            try:
                return cls[value]
            except KeyError:
                # Try as int string
                try:
                    return cls(int(value))
                except Exception:
                    pass
        raise ValueError(f"Cannot convert {value!r} to {cls.__name__}")

    @classmethod
    def list_from(cls, values):
        """Convert a list of mixed values to a list of StateCommand enums."""
        if values is None:
            return []
        return [cls.from_value(v) for v in values]

class State(Enum):
    """Enum for system states of the Motorcortex server."""
    INIT_S = 0
    OFF_S = 1
    IDLE_S = 2
    PAUSED_S = 3
    ENGAGED_S = 4
    HOMING_S = 5
    FORCEDIDLE_S = 6
    ESTOP_OFF_S = 7
    OFF_TO_IDLE_T = 102
    OFF_TO_REFERENCING_T = 105
    IDLE_TO_OFF_T = 201
    PAUSED_TO_IDLE_T = 302
    IDLE_TO_ENGAGED_T = 204
    ENGAGED_TO_PAUSED_T = 403
    TO_FORCEDIDLE_T = 600
    RESET_FORCEDIDLE_T = 602
    TO_ESTOP_T = 700
    RESET_ESTOP_T = 701

    @classmethod
    def from_value(cls, value):
        """Convert int, str, or enum to State."""
        if isinstance(value, cls):
            return value
        if isinstance(value, int):
            return cls(value)
        if isinstance(value, str):
            try:
                return cls[value]
            except KeyError:
                # Try as int string
                try:
                    return cls(int(value))
                except Exception:
                    pass
        raise ValueError(f"Cannot convert {value!r} to {cls.__name__}")

    @classmethod
    def list_from(cls, values):
        """Convert a list of mixed values to a list of State enums."""
        if values is None:
            return []
        return [cls.from_value(v) for v in values]