"""Control ventilation units with the VENTS A21 controller over Modbus TCP."""

from .alarms import (
    ALARM_CODES,
    FILTER_ALARM_CODES,
    Alarm,
    Severity,
    describe_alarm,
)
from .client import (
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    A21Client,
    CoilWrite,
    RegisterWrite,
    Write,
)
from .modbus import (
    A21ConnectionError,
    A21Error,
    A21ProtocolError,
    A21RequestRefused,
)
from .state import A21State, BypassMode, FanRegulation, FilterState, OperationMode

__all__ = [
    "ALARM_CODES",
    "DEFAULT_PORT",
    "DEFAULT_UNIT_ID",
    "FILTER_ALARM_CODES",
    "A21Client",
    "A21ConnectionError",
    "A21Error",
    "A21ProtocolError",
    "A21RequestRefused",
    "A21State",
    "Alarm",
    "BypassMode",
    "CoilWrite",
    "FanRegulation",
    "FilterState",
    "OperationMode",
    "RegisterWrite",
    "Severity",
    "Write",
    "describe_alarm",
]
