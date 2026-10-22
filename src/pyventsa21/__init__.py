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
from .identity import (
    APP_PORT,
    DEFAULT_DEVICE_PASSWORD,
    async_probe,
    async_read_identifier,
)
from .modbus import (
    A21ConnectionError,
    A21Error,
    A21ProtocolError,
    A21RequestRefused,
    ConnectionStats,
)
from .state import (
    A21State,
    BypassMode,
    EfficiencyStatus,
    FanRegulation,
    FilterState,
    OperationMode,
)

__all__ = [
    "ALARM_CODES",
    "APP_PORT",
    "DEFAULT_DEVICE_PASSWORD",
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
    "ConnectionStats",
    "EfficiencyStatus",
    "FanRegulation",
    "FilterState",
    "OperationMode",
    "RegisterWrite",
    "Severity",
    "Write",
    "async_probe",
    "async_read_identifier",
    "describe_alarm",
]
