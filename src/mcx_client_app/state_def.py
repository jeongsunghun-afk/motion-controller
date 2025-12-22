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