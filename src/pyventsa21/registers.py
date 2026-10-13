"""Modbus addresses of the A21 controller.

From the VENTS document "Modbus table for connecting A21 automation to BMS"
(V55-8-1EN-02). Names follow the table: CL_ coils, DI_ discrete inputs,
IR_ input registers, HR_ holding registers.

Registers made of several bytes put the first field of the table in the high
byte (for example IR_TIMER_MIN_SEC is minutes << 8 | seconds).
"""

from __future__ import annotations

from typing import Final

DEVICE_TYPE_A21: Final = 1

# --- Coils (functions 1, 5) -------------------------------------------------
CL_POWER: Final = 0
CL_TIMER: Final = 1
CL_WEEK: Final = 2
CL_BOOST_MODE: Final = 3  # read only
CL_FIREPLACE_MODE: Final = 4  # read only
CL_INT_RH_CTRL: Final = 5
CL_EXT_RH_CTRL: Final = 6
CL_INT_CO2_CTRL: Final = 7
CL_EXT_CO2_CTRL: Final = 8
CL_INT_PM25_CTRL: Final = 9
CL_EXT_PM25_CTRL: Final = 10
CL_INT_VOC_CTRL: Final = 11
CL_EXT_VOC_CTRL: Final = 12
CL_BOOST_SWITCH_CTRL: Final = 13
CL_FIREPLACE_SWITCH_CTRL: Final = 14
CL_FIRE_ALARM_CTRL: Final = 15
CL_10V_SENSOR_CTRL: Final = 16
CL_RESET_FILTER_TIMER: Final = 17  # write only
CL_RESET_ALARM: Final = 18  # write only
CL_RESTORE_FACTORY: Final = 19  # write only; the client refuses to write it
CL_CLOUD_CTRL: Final = 20
CL_MIN_SUPPLY_TEMP_CTRL: Final = 21
CL_WATER_PRESSURE_CTRL: Final = 22
CL_WATER_FLOW_CTRL: Final = 23
CL_WATER_AUTO_RESTART: Final = 24
CL_AUTO_AIRFLOW_REDUCTION: Final = 25
COIL_COUNT: Final = 26

# --- Discrete inputs (function 2) -------------------------------------------
DI_BOOST_SWITCH: Final = 0
DI_FIREPLACE_SWITCH: Final = 1
DI_FIRE_ALARM: Final = 2
DI_STATUS_RH: Final = 3
DI_STATUS_CO2: Final = 4
DI_STATUS_PM25: Final = 5
DI_STATUS_VOC: Final = 6
DI_STATUS_HEATER: Final = 7
DI_STATUS_COOLER: Final = 8
DI_STATUS_FAN_BLOWING: Final = 9
DI_PREHEATER_THERMOSTAT: Final = 10
DI_HEATER_THERMOSTAT: Final = 11
DI_SUPPLY_FILTER_SWITCH: Final = 12
DI_EXTRACT_FILTER_SWITCH: Final = 13
DI_WATER_PRESSURE: Final = 14
DI_WATER_FLOW: Final = 15
DI_SUPPLY_FAN_SWITCH: Final = 16
DI_EXTRACT_FAN_SWITCH: Final = 17
DI_WATER_PREHEATING: Final = 18
DI_ALARM_FIRST: Final = 19  # alarm codes 0 to 52 are inputs 19 to 71
ALARM_CODE_COUNT: Final = 53
DISCRETE_COUNT: Final = 72

# --- Input registers (function 4) -------------------------------------------
IR_TEMP_SELECTED: Final = 0  # the probe the unit regulates on
IR_TEMP_OUTDOOR: Final = 1  # outdoor air entering the unit, before preheating
IR_TEMP_SUPPLY: Final = 2  # supply air leaving the unit, after the reheater
IR_TEMP_EXTRACT: Final = 3  # extract air entering the unit
IR_TEMP_EXHAUST: Final = 4  # exhaust air leaving the unit
IR_TEMP_PANEL: Final = 5
IR_TEMP_AFTER_PREHEATER: Final = 6
IR_TEMP_BEFORE_REHEATER: Final = 7
IR_TEMP_WATER: Final = 8
IR_RTC_BATTERY: Final = 9  # mV
IR_RH_INT: Final = 10
IR_RH_EXT: Final = 11
IR_CO2_INT: Final = 12
IR_CO2_EXT: Final = 13
IR_PM25_INT: Final = 14
IR_PM25_EXT: Final = 15
IR_VOC_INT: Final = 16
IR_VOC_EXT: Final = 17
IR_10V_SENSOR: Final = 18
IR_SUPPLY_FLOW: Final = 19
IR_EXTRACT_FLOW: Final = 20
IR_SUPPLY_PRESSURE: Final = 21
IR_EXTRACT_PRESSURE: Final = 22
IR_SUPPLY_RPM: Final = 23
IR_EXTRACT_RPM: Final = 24
IR_TIMER_MIN_SEC: Final = 25  # high byte: minutes, low byte: seconds
IR_TIMER_HOURS: Final = 26  # low byte: hours
IR_FILTER_HOURS_MIN: Final = 27  # high byte: hours, low byte: minutes
IR_FILTER_DAYS: Final = 28
IR_WORK_HOURS_MIN: Final = 29  # high byte: hours, low byte: minutes
IR_WORK_DAYS: Final = 30
IR_FILTER_STATE: Final = 31
IR_WEEK_SPEED: Final = 32
IR_WEEK_TEMP: Final = 33
IR_FIRMWARE: Final = 34  # 34: major/minor, 35: day/month, 36: year
IR_DEVICE_TYPE: Final = 37
IR_ALARM: Final = 38  # 0: none, 1: alarm, 2: warning
IR_RH_DEMAND: Final = 39
IR_CO2_DEMAND: Final = 40
IR_PM25_DEMAND: Final = 41
IR_VOC_DEMAND: Final = 42
IR_PREHEATER_OUTPUT: Final = 43
IR_REHEATER_OUTPUT: Final = 44
IR_BYPASS_OUTPUT: Final = 45
IR_COOLER_OUTPUT: Final = 46
IR_WATER_OUTPUT: Final = 47
IR_SUPPLY_SETPOINT: Final = 48
IR_WATER_STANDBY_SETPOINT: Final = 49
IR_WATER_START_SETPOINT: Final = 50
IR_BYPASS_STATE: Final = 51  # 0: closed, 100: open (or rotary exchanger stopped)
IR_SUPPLY_FAN_PERCENT: Final = 52
IR_EXTRACT_FAN_PERCENT: Final = 53
INPUT_COUNT: Final = 54

# --- Holding registers (functions 3, 6) -------------------------------------
HR_VENTILATION_MODE: Final = 0  # 0: percent, 1: constant airflow, 2: constant pressure
HR_MAX_SPEED_MODE: Final = 1  # number of preset speeds, 3 to 5
HR_SPEED_MODE: Final = 2  # 1..5, 255: manual
HR_MIN_SPEED: Final = 3
HR_MAX_SPEED: Final = 4
HR_SUPPLY_SPEED0: Final = 5  # supply/extract pairs, standby then speeds 1-5 (5-16)
HR_MANUAL_SPEED: Final = 17
HR_BLOWING_SPEED: Final = 18
HR_BOOST_SUPPLY_SPEED: Final = 19
HR_BOOST_EXTRACT_SPEED: Final = 20
HR_FIREPLACE_SUPPLY_SPEED: Final = 21
HR_FIREPLACE_EXTRACT_SPEED: Final = 22
HR_MIN_AIRFLOW: Final = 23
HR_MAX_AIRFLOW: Final = 24
HR_SUPPLY_FLOW0: Final = 25  # supply/extract pairs, standby then speeds 1-5 (25-36)
HR_MIN_PRESSURE: Final = 37
HR_MAX_PRESSURE: Final = 38
HR_SUPPLY_PRESSURE0: Final = 39  # supply/extract pairs, standby and speed 1 (39-42)
HR_OPERATION_MODE: Final = 43  # 0: ventilation, 1: heating, 2: cooling, 3: auto
HR_SET_TEMP: Final = 44
HR_SET_RH: Final = 45
HR_SET_CO2: Final = 46
HR_SET_PM25: Final = 47
HR_SET_VOC: Final = 48
HR_TIMER_MODE: Final = 49  # 0: standby, 1..5: speed
HR_TIMER_TEMP: Final = 50  # 0: ventilation only, 15..30 °C
HR_TIMER_TIME: Final = 51  # high byte: hours, low byte: minutes
HR_WINTER_SUMMER_TEMP: Final = 52
HR_TEMP_SENSOR: Final = 53  # 0: extract air, 1: control panel, 2: supply air
HR_MAIN_HEATER_TYPE: Final = 54  # 0: none, 1: electric, 2: water
HR_COOLER_TYPE: Final = 55  # 0: none, 1: on/off, 2: analogue
HR_DEFROST_MODE: Final = 56  # 0: off, 1: preheating, 2: bypass/rotor, 3: fans
HR_BYPASS_TYPE: Final = 57  # 0: none, 1: on/off, 2: analogue, 3/4: rotary, 5: 3-point
HR_FILTER_TIMER: Final = 58  # 0: off, 70..365 days
HR_BOOST_OFF_DELAY: Final = 59
HR_BOOST_ON_DELAY: Final = 60
HR_RTC_MIN_SEC: Final = 61  # high byte: minutes, low byte: seconds
HR_RTC_HOURS: Final = 62  # low byte: hours
HR_RTC_DAY_WEEKDAY: Final = 63  # high byte: day of the month, low byte: weekday 1-7
HR_RTC_MONTH_YEAR: Final = 64  # high byte: month, low byte: year on two digits
HR_CO2_SENSOR_RANGE: Final = 65
HR_PM25_SENSOR_RANGE: Final = 66
HR_MIN_SUPPLY_TEMP: Final = 67
HR_HEATER_MODE: Final = 68  # 1: manual, 2: auto
HR_HEATER_MANUAL: Final = 69
HR_COOLER_MODE: Final = 70  # 1: manual, 2: auto
HR_COOLER_MANUAL: Final = 71
HR_PREHEATER_MODE: Final = 72  # 1: manual, 2: auto
HR_PREHEATER_MANUAL: Final = 73
HR_BYPASS_MODE: Final = 74  # 0: closed, 1: open, 2: auto
HR_BYPASS_MANUAL: Final = 75
HR_PID_FIRST: Final = 76  # nine regulators x (Kp, Ki, Kd), 76 to 102
HR_FAN_ALARM_CTRL: Final = 103  # 0: none, 1..254: tacho pulses, 255: pressure switch
HR_FAN_ALARM_TIME: Final = 104
HR_DAMPER_OPENING_TIME: Final = 105
HR_BLOWDOWN_TIME: Final = 106
HR_COOLER_MIN_OFF: Final = 107
HR_COOLER_MIN_ON: Final = 108
HR_COOLER_HYSTERESIS: Final = 109
HR_BYPASS_SIDE: Final = 110  # 0: bypasses the outdoor air, 1: the extract air
HR_BYPASS_OPENING_TIME: Final = 111
HR_CORRECTION_FIRST: Final = 112  # six probe corrections, tenths of °C, 112 to 117
HR_WATER_VALVE_MIN: Final = 118
HR_WATER_START_TIMEOUT: Final = 119
HR_WATER_MIN_START_TEMP: Final = 120
HR_WATER_MAX_START_TEMP: Final = 121
HR_WATER_MIN_ALARM_TEMP: Final = 122
HR_WATER_MAX_ALARM_TEMP: Final = 123
# 124-125 hold the engineering menu password: the client never reads them
# and refuses to write them.
HR_ENGINEER_PASSWORD: Final = 124
HOLDING_COUNT: Final = 124

SPEED_MANUAL: Final = 255
TEMP_NO_SENSOR: Final = 0x8000
TEMP_SHORT_CIRCUIT: Final = 0x7FFF
ROTARY_EXCHANGER_TYPES: Final = frozenset({3, 4})
