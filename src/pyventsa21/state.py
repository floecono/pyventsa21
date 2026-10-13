"""One snapshot of an A21 controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from .alarms import Alarm, Severity, describe_alarm
from .registers import (
    ALARM_CODE_COUNT,
    CL_BOOST_MODE,
    CL_POWER,
    CL_TIMER,
    CL_WEEK,
    DI_ALARM_FIRST,
    DI_STATUS_COOLER,
    DI_STATUS_HEATER,
    HR_BYPASS_MODE,
    HR_BYPASS_TYPE,
    HR_MANUAL_SPEED,
    HR_MAX_SPEED_MODE,
    HR_OPERATION_MODE,
    HR_SET_TEMP,
    HR_SPEED_MODE,
    HR_VENTILATION_MODE,
    IR_ALARM,
    IR_BYPASS_STATE,
    IR_DEVICE_TYPE,
    IR_FILTER_DAYS,
    IR_FILTER_STATE,
    IR_FIRMWARE,
    IR_PREHEATER_OUTPUT,
    IR_RH_INT,
    IR_TEMP_EXHAUST,
    IR_TEMP_EXTRACT,
    IR_TEMP_OUTDOOR,
    IR_TEMP_SELECTED,
    IR_TEMP_SUPPLY,
    IR_TIMER_HOURS,
    IR_TIMER_MIN_SEC,
    IR_WORK_DAYS,
    IR_WORK_HOURS_MIN,
    ROTARY_EXCHANGER_TYPES,
    SPEED_MANUAL,
    TEMP_NO_SENSOR,
    TEMP_SHORT_CIRCUIT,
)

# Below this indoor/outdoor difference the efficiency figure is only noise.
_MIN_EFFICIENCY_DELTA = 5.0


class OperationMode(IntEnum):
    """What the unit does with the air temperature."""

    VENTILATION = 0
    HEATING = 1
    COOLING = 2
    AUTO = 3


class BypassMode(IntEnum):
    """How the bypass (or rotary exchanger) is driven."""

    CLOSED = 0
    OPEN = 1
    AUTO = 2


class FanRegulation(IntEnum):
    """What the fan settings of each speed are expressed in."""

    PERCENT = 0
    AIRFLOW = 1
    PRESSURE = 2


class FilterState(IntEnum):
    """What the controller says about the filters."""

    CLEAN = 0
    SUPPLY_CLOGGED = 1
    EXTRACT_CLOGGED = 2
    REPLACE = 3


def _signed(value: int) -> int:
    return value - 0x10000 if value > 0x7FFF else value


def _enum[E: IntEnum](kind: type[E], raw: int | None) -> E | None:
    try:
        return None if raw is None else kind(raw)
    except ValueError:
        return None


@dataclass(slots=True)
class A21State:
    """Everything read from the controller in one poll.

    The four tables are kept raw and indexed by Modbus address; use the
    constants of ``pyventsa21.registers``. A value is None when the firmware
    does not expose that address (older firmware has shorter tables).

    The properties decode the values most applications need.
    """

    coils: list[bool | None]
    discrete: list[bool | None]
    inputs: list[int | None]
    holdings: list[int | None]

    # --- raw access ---------------------------------------------------------
    def coil(self, address: int) -> bool | None:
        """Return a coil."""
        return self.coils[address]

    def di(self, address: int) -> bool | None:
        """Return a discrete input."""
        return self.discrete[address]

    def ir(self, address: int) -> int | None:
        """Return a raw input register."""
        return self.inputs[address]

    def hr(self, address: int) -> int | None:
        """Return a raw holding register."""
        return self.holdings[address]

    def temperature(self, address: int) -> float | None:
        """Return an input register as °C, None without a working probe."""
        raw = self.inputs[address]
        if raw is None or raw in (TEMP_NO_SENSOR, TEMP_SHORT_CIRCUIT):
            return None
        return _signed(raw) / 10

    # --- operation ----------------------------------------------------------
    @property
    def device_type(self) -> int | None:
        """Return the controller type (1 for an A21)."""
        return self.inputs[IR_DEVICE_TYPE]

    @property
    def is_on(self) -> bool:
        """Return True when the unit is switched on."""
        return bool(self.coils[CL_POWER])

    @property
    def operation_mode(self) -> OperationMode | None:
        """Return the operation mode."""
        return _enum(OperationMode, self.holdings[HR_OPERATION_MODE])

    @property
    def speed(self) -> int | None:
        """Return the preset speed in use (1 to 5), None in manual speed."""
        raw = self.holdings[HR_SPEED_MODE]
        return None if raw == SPEED_MANUAL else raw

    @property
    def is_manual_speed(self) -> bool:
        """Return True when the fans follow the manual speed."""
        return self.holdings[HR_SPEED_MODE] == SPEED_MANUAL

    @property
    def manual_speed(self) -> int | None:
        """Return the manual speed in percent."""
        return self.holdings[HR_MANUAL_SPEED]

    @property
    def max_speed(self) -> int:
        """Return the number of preset speeds (3 to 5)."""
        raw = self.holdings[HR_MAX_SPEED_MODE]
        return min(max(raw, 1), 5) if raw else 3

    @property
    def fan_regulation(self) -> FanRegulation | None:
        """Return how the fans are regulated."""
        return _enum(FanRegulation, self.holdings[HR_VENTILATION_MODE])

    @property
    def target_temperature(self) -> int | None:
        """Return the temperature setpoint in °C."""
        return self.holdings[HR_SET_TEMP]

    @property
    def is_boosting(self) -> bool:
        """Return True while boost mode runs."""
        return bool(self.coils[CL_BOOST_MODE])

    @property
    def is_timer_on(self) -> bool:
        """Return True while the main timer runs."""
        return bool(self.coils[CL_TIMER])

    @property
    def is_schedule_on(self) -> bool:
        """Return True when the weekly schedule drives the unit."""
        return bool(self.coils[CL_WEEK])

    @property
    def timer_remaining(self) -> int | None:
        """Return the seconds left on the main timer."""
        min_sec, hours = self.inputs[IR_TIMER_MIN_SEC], self.inputs[IR_TIMER_HOURS]
        if min_sec is None or hours is None:
            return None
        return (hours & 0xFF) * 3600 + (min_sec >> 8) * 60 + (min_sec & 0xFF)

    # --- air ----------------------------------------------------------------
    @property
    def control_temperature(self) -> float | None:
        """Return the temperature the unit regulates on."""
        return self.temperature(IR_TEMP_SELECTED)

    @property
    def outdoor_temperature(self) -> float | None:
        """Return the temperature of the outdoor air entering the unit."""
        return self.temperature(IR_TEMP_OUTDOOR)

    @property
    def supply_temperature(self) -> float | None:
        """Return the temperature of the air supplied to the rooms."""
        return self.temperature(IR_TEMP_SUPPLY)

    @property
    def extract_temperature(self) -> float | None:
        """Return the temperature of the air extracted from the rooms."""
        return self.temperature(IR_TEMP_EXTRACT)

    @property
    def exhaust_temperature(self) -> float | None:
        """Return the temperature of the air exhausted outdoors."""
        return self.temperature(IR_TEMP_EXHAUST)

    @property
    def humidity(self) -> int | None:
        """Return the humidity of the main probe, None without one."""
        return self.inputs[IR_RH_INT] or None

    @property
    def efficiency(self) -> int | None:
        """Return the supply-side heat recovery efficiency in percent.

        (supply - outdoor) / (extract - outdoor). Only meaningful while the
        exchanger alone changes the supply temperature, so nothing is
        reported when a heater or cooler runs or when the bypass is open.
        """
        outdoor = self.outdoor_temperature
        supply = self.supply_temperature
        extract = self.extract_temperature
        if outdoor is None or supply is None or extract is None or not self.is_on:
            return None
        if self.discrete[DI_STATUS_HEATER] or self.discrete[DI_STATUS_COOLER]:
            return None
        if self.inputs[IR_BYPASS_STATE] or self.inputs[IR_PREHEATER_OUTPUT]:
            return None
        delta = extract - outdoor
        if abs(delta) < _MIN_EFFICIENCY_DELTA:
            return None
        return round(min(max((supply - outdoor) / delta, 0.0), 1.0) * 100)

    # --- exchanger ----------------------------------------------------------
    @property
    def has_bypass(self) -> bool:
        """Return True when the unit has a bypass or a rotary exchanger."""
        return bool(self.holdings[HR_BYPASS_TYPE])

    @property
    def has_rotary_exchanger(self) -> bool:
        """Return True for a rotary exchanger instead of a bypass damper."""
        return self.holdings[HR_BYPASS_TYPE] in ROTARY_EXCHANGER_TYPES

    @property
    def bypass_position(self) -> int | None:
        """Return the bypass opening in percent (0 closed, 100 open).

        With a rotary exchanger, 100 means the wheel is stopped.
        """
        return self.inputs[IR_BYPASS_STATE] if self.has_bypass else None

    @property
    def bypass_mode(self) -> BypassMode | None:
        """Return how the bypass is driven."""
        if not self.has_bypass:
            return None
        return _enum(BypassMode, self.holdings[HR_BYPASS_MODE])

    # --- maintenance --------------------------------------------------------
    @property
    def filter_state(self) -> FilterState | None:
        """Return the state of the filters."""
        return _enum(FilterState, self.inputs[IR_FILTER_STATE])

    @property
    def filter_days_remaining(self) -> int | None:
        """Return the days left before the filter replacement timer expires."""
        return self.inputs[IR_FILTER_DAYS]

    @property
    def operating_hours(self) -> int | None:
        """Return the motor run time in hours."""
        hours_min, days = self.inputs[IR_WORK_HOURS_MIN], self.inputs[IR_WORK_DAYS]
        if hours_min is None or days is None:
            return None
        return days * 24 + (hours_min >> 8)

    @property
    def firmware(self) -> str | None:
        """Return the firmware version, e.g. '2.15 (2023-04-18)'."""
        version, date, year = self.inputs[IR_FIRMWARE : IR_FIRMWARE + 3]
        if version is None:
            return None
        text = f"{version >> 8}.{version & 0xFF}"
        if date and year:
            text += f" ({year}-{date & 0xFF:02d}-{date >> 8:02d})"
        return text

    # --- alarms -------------------------------------------------------------
    @property
    def alarm_codes(self) -> list[int]:
        """Return the active alarm codes (0 to 52)."""
        return [
            code
            for code in range(ALARM_CODE_COUNT)
            if self.discrete[DI_ALARM_FIRST + code]
        ]

    @property
    def alarms(self) -> list[Alarm]:
        """Return the active alarms and warnings, described."""
        # IR_ALARM: 1 when at least one alarm is active, 2 for warnings only.
        fallback = Severity.ALARM if self.inputs[IR_ALARM] == 1 else Severity.WARNING
        return [describe_alarm(code, fallback) for code in self.alarm_codes]

    @property
    def severity(self) -> Severity | None:
        """Return the worst severity among the active codes, None without any."""
        raw = self.inputs[IR_ALARM]
        if raw == 1:
            return Severity.ALARM
        return Severity.WARNING if raw == 2 else None
