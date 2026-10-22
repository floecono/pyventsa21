"""Decoding of the raw tables."""

from __future__ import annotations

from pyventsa21 import (
    ALARM_CODES,
    A21Client,
    BypassMode,
    EfficiencyStatus,
    FilterState,
    Severity,
    describe_alarm,
)

from .simulator import A21Simulator


def test_alarm_table() -> None:
    assert sorted(ALARM_CODES) == list(range(46))
    assert ALARM_CODES[0] == (Severity.ALARM, "Supply fan fault")
    assert ALARM_CODES[38][0] is Severity.WARNING
    unknown = describe_alarm(50, Severity.ALARM)
    assert (unknown.description, unknown.severity, unknown.documented) == (
        "Code 50",
        Severity.ALARM,
        False,
    )


async def test_alarms(client: A21Client, simulator: A21Simulator) -> None:
    state = await client.read_state()
    assert state.alarms == [] and state.severity is None

    simulator.set_input(38, 1)
    for code in (0, 38, 50):
        simulator.set_discrete(19 + code, True)
    state = await client.read_state()
    assert state.alarm_codes == [0, 38, 50]
    assert state.severity is Severity.ALARM
    assert [(a.code, a.severity, a.description) for a in state.alarms] == [
        (0, Severity.ALARM, "Supply fan fault"),
        (38, Severity.WARNING, "Bypass in manual mode"),
        (50, Severity.ALARM, "Code 50"),
    ]


async def test_temperatures(client: A21Client, simulator: A21Simulator) -> None:
    simulator.set_temperature(1, -7.5)
    state = await client.read_state()
    assert state.outdoor_temperature == -7.5
    assert state.temperature(5) is None  # no probe: 0x8000
    simulator.set_input(4, 0x7FFF)  # short circuit
    assert (await client.read_state()).exhaust_temperature is None


async def test_efficiency(client: A21Client, simulator: A21Simulator) -> None:
    # (19.2 - 6.3) / (21.4 - 6.3) = 85.4 %
    state = await client.read_state()
    assert state.efficiency == 85
    assert state.efficiency_status is EfficiencyStatus.MEASURED
    # Exhaust side: (21.4 - 8.9) / (21.4 - 6.3) = 82.8 %
    assert state.efficiency_exhaust_side == 83
    # Apparent flow ratio: (19.2 - 6.3) / (21.4 - 8.9) = 1.03
    assert state.flow_ratio == 1.03

    simulator.set_input(51, 100)  # bypass open
    state = await client.read_state()
    assert (
        state.efficiency is None and state.efficiency_status is EfficiencyStatus.BYPASS
    )
    assert state.efficiency_exhaust_side is None and state.flow_ratio is None
    simulator.set_input(51, 0)
    simulator.set_temperature(1, 19.0)  # outdoor almost as warm as indoor
    state = await client.read_state()
    assert state.efficiency is None
    assert state.efficiency_status is EfficiencyStatus.SMALL_DIFFERENCE
    simulator.set_temperature(1, 6.3)
    simulator.set_coil(0, False)  # unit off
    state = await client.read_state()
    assert state.efficiency is None and state.efficiency_status is EfficiencyStatus.OFF
    simulator.set_coil(0, True)
    simulator.set_input(23, 0)  # supply fan stopped, extract fan running
    state = await client.read_state()
    assert state.defrosting
    assert state.efficiency is None
    assert state.efficiency_status is EfficiencyStatus.DEFROSTING
    simulator.set_input(23, 1480)
    simulator.set_input(2, 0x8000)  # no supply probe
    assert (await client.read_state()).efficiency_status is EfficiencyStatus.NO_PROBE


async def test_unbalanced_flows(client: A21Client, simulator: A21Simulator) -> None:
    """Twice as much extract as supply: the supply side looks better than it is."""
    simulator.set_temperature(2, 20.0)  # supply warmed almost to indoor
    simulator.set_temperature(4, 14.5)  # exhaust gave up little
    state = await client.read_state()
    assert state.efficiency == 91
    assert state.efficiency_exhaust_side == 46
    assert state.flow_ratio == 1.99


async def test_condensation(client: A21Client, simulator: A21Simulator) -> None:
    # Extract 21.4 °C at 47 % RH: dew point 9.6 °C; exhaust 8.9 °C condenses.
    state = await client.read_state()
    assert state.dew_point == 9.6
    assert state.condensation_likely is True
    simulator.set_temperature(4, 11.0)
    assert (await client.read_state()).condensation_likely is False
    # Without a humidity probe, cold exhaust air is taken to be condensing.
    simulator.set_input(10, 0)
    state = await client.read_state()
    assert state.dew_point is None and state.condensation_likely is False
    simulator.set_temperature(4, 7.5)
    assert (await client.read_state()).condensation_likely is True
    # The external probe (input 11) stands in for the internal one.
    simulator.set_input(11, 60)
    state = await client.read_state()
    assert state.humidity == 60 and state.dew_point == 13.3
    simulator.set_input(4, 0x8000)  # no exhaust probe
    assert (await client.read_state()).condensation_likely is None


async def test_bypass(client: A21Client, simulator: A21Simulator) -> None:
    state = await client.read_state()
    assert state.has_bypass and not state.has_rotary_exchanger
    assert state.bypass_position == 0 and state.bypass_mode is BypassMode.AUTO
    simulator.set_holding(57, 4)
    assert (await client.read_state()).has_rotary_exchanger
    simulator.set_holding(57, 0)
    state = await client.read_state()
    assert state.bypass_position is None and state.bypass_mode is None


async def test_maintenance(client: A21Client, simulator: A21Simulator) -> None:
    state = await client.read_state()
    assert state.filter_state is FilterState.CLEAN
    assert state.filter_days_remaining == 62
    assert state.operating_hours == 412 * 24 + 7
    assert state.timer_remaining == 3600 + 12 * 60 + 34
    assert state.humidity == 47
    simulator.set_input(31, 3)
    simulator.set_input(10, 0)
    state = await client.read_state()
    assert state.filter_state is FilterState.REPLACE
    assert state.humidity is None
