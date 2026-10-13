"""Alarm codes of the A21 controller.

The Modbus table only numbers the codes (discrete inputs 19 to 71 are codes
0 to 52). Their meaning comes from the installer manual of the units, which
documents codes 0 to 45.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Severity(StrEnum):
    """How serious an active code is.

    An alarm stops the unit and must be reset by hand. A warning leaves the
    unit running and clears by itself once its cause is gone.
    """

    ALARM = "alarm"
    WARNING = "warning"


# code: (severity, description)
ALARM_CODES: Final[dict[int, tuple[Severity, str]]] = {
    0: (Severity.ALARM, "Supply fan fault"),
    1: (Severity.ALARM, "Extract fan fault"),
    2: (Severity.ALARM, "Outdoor air sensor missing"),
    3: (Severity.ALARM, "Outdoor air sensor shorted"),
    4: (Severity.ALARM, "Supply air sensor missing"),
    5: (Severity.ALARM, "Supply air sensor shorted"),
    6: (Severity.ALARM, "Extract air sensor missing"),
    7: (Severity.ALARM, "Extract air sensor shorted"),
    8: (Severity.ALARM, "Exhaust air sensor missing"),
    9: (Severity.ALARM, "Exhaust air sensor shorted"),
    10: (Severity.ALARM, "Preheater safety thermostat tripped"),
    11: (Severity.ALARM, "Heater safety thermostat tripped"),
    12: (Severity.ALARM, "Preheating can no longer protect the exchanger from frost"),
    13: (Severity.WARNING, "Humidity sensor not detected"),
    14: (Severity.WARNING, "CO₂ sensor not detected"),
    15: (Severity.WARNING, "PM2.5 sensor not detected"),
    16: (Severity.WARNING, "VOC sensor not detected"),
    17: (Severity.WARNING, "External humidity sensor not detected"),
    18: (Severity.WARNING, "External CO₂ sensor not detected"),
    19: (Severity.WARNING, "External PM2.5 sensor not detected"),
    20: (Severity.WARNING, "External VOC sensor not detected"),
    21: (Severity.WARNING, "No room temperature from the control panel"),
    22: (Severity.WARNING, "Exchanger frost risk"),
    23: (Severity.WARNING, "Clock battery low"),
    24: (Severity.WARNING, "Outdoor air filter clogged"),
    25: (Severity.ALARM, "Fire alarm"),
    26: (Severity.ALARM, "Supply air too cold"),
    27: (Severity.ALARM, "Return water sensor missing"),
    28: (Severity.ALARM, "Return water sensor shorted"),
    29: (Severity.WARNING, "Extract air filter clogged"),
    30: (Severity.ALARM, "No water pressure"),
    31: (Severity.ALARM, "No water flow"),
    32: (Severity.ALARM, "Return water too cold"),
    33: (
        Severity.ALARM,
        "Stopping the supply fan can no longer protect the exchanger from frost",
    ),
    34: (Severity.ALARM, "The bypass can no longer protect the exchanger from frost"),
    35: (Severity.WARNING, "Frost protection disabled"),
    36: (Severity.WARNING, "Heater in manual mode"),
    37: (Severity.WARNING, "Cooler in manual mode"),
    38: (Severity.WARNING, "Bypass in manual mode"),
    39: (Severity.WARNING, "Rotary exchanger in manual mode"),
    40: (Severity.WARNING, "Filter timer expired"),
    41: (Severity.WARNING, "Rotary exchanger malfunction"),
    42: (Severity.WARNING, "Preheater in manual mode"),
    43: (Severity.ALARM, "Return water too cold to start"),
    44: (Severity.WARNING, "Bypass frost protection replaced by supply fan protection"),
    45: (Severity.WARNING, "Fireplace mode locked by the frost protection"),
}

# Codes that only say "change the filters".
FILTER_ALARM_CODES: Final = frozenset({24, 29, 40})


@dataclass(frozen=True, slots=True)
class Alarm:
    """One active alarm or warning."""

    code: int
    severity: Severity
    description: str
    # False for a code the manual does not document (46 to 52).
    documented: bool = True


def describe_alarm(code: int, fallback: Severity = Severity.WARNING) -> Alarm:
    """Describe one code.

    A code the manual does not document keeps its number as description and
    takes the fallback severity (the overall severity the controller reports).
    """
    known = ALARM_CODES.get(code)
    if known is None:
        return Alarm(code, fallback, f"Code {code}", documented=False)
    severity, description = known
    return Alarm(code, severity, description)
