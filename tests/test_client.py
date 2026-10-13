"""The client against the simulated controller."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from pyventsa21 import (
    A21Client,
    A21ConnectionError,
    A21RequestRefused,
    BypassMode,
    CoilWrite,
    OperationMode,
    RegisterWrite,
)

from .simulator import A21Simulator


async def test_identify(client: A21Client, simulator: A21Simulator) -> None:
    assert await client.identify() == 1
    assert await client.is_a21()
    simulator.set_input(37, 7)
    assert not await client.is_a21()


async def test_read_state(client: A21Client) -> None:
    state = await client.read_state()
    assert state.is_on
    assert state.operation_mode is OperationMode.AUTO
    assert state.speed == 2 and not state.is_manual_speed
    assert state.max_speed == 3
    assert state.target_temperature == 23
    assert state.outdoor_temperature == 6.3
    assert state.supply_temperature == 19.2
    assert state.firmware == "2.15 (2023-04-18)"
    assert len(state.holdings) == 124


async def test_password_registers_are_never_read(
    client: A21Client, simulator: A21Simulator
) -> None:
    await client.read_state()
    reads = [(a, n) for f, a, n in simulator.requests if f == 3]
    assert reads and all(address + count <= 124 for address, count in reads)


async def test_commands(client: A21Client, simulator: A21Simulator) -> None:
    state = await client.turn_off()
    assert not state.is_on and simulator.get_coil(0) is False
    state = await client.turn_on()
    assert state.is_on

    state = await client.set_operation_mode(OperationMode.HEATING)
    assert simulator.get_holding(43) == 1
    assert state.operation_mode is OperationMode.HEATING

    state = await client.set_speed(3)
    assert simulator.get_holding(2) == 3 and state.speed == 3

    state = await client.set_manual_speed(65)
    assert simulator.get_holding(17) == 65 and simulator.get_holding(2) == 255
    assert state.is_manual_speed and state.speed is None and state.manual_speed == 65

    await client.set_temperature(25)
    assert simulator.get_holding(44) == 25

    state = await client.set_bypass_mode(BypassMode.OPEN)
    assert simulator.get_holding(74) == 1 and state.bypass_mode is BypassMode.OPEN

    await client.set_timer(True)
    assert simulator.get_coil(1) is True
    await client.set_schedule(True)
    assert simulator.get_coil(2) is True
    await client.reset_alarms()
    assert simulator.get_coil(18) is True
    await client.reset_filter_timer()
    assert simulator.get_coil(17) is True


async def test_values_are_checked_before_sending(
    client: A21Client, simulator: A21Simulator
) -> None:
    for call in (
        client.set_speed(0),
        client.set_speed(6),
        client.set_manual_speed(101),
        client.set_temperature(14),
        client.set_temperature(31),
    ):
        with pytest.raises(ValueError):
            await call
    assert not [r for r in simulator.requests if r[0] in (5, 6)]


async def test_forbidden_writes(client: A21Client, simulator: A21Simulator) -> None:
    """Factory reset and the engineer password are out of reach."""
    with pytest.raises(ValueError):
        await client.write_coil(19, True)
    with pytest.raises(ValueError):
        await client.write_register(124, 0x3131)
    with pytest.raises(ValueError):
        await client.write(RegisterWrite(2, 1), CoilWrite(19, True))
    # Nothing was sent, not even the valid write queued before the refused one.
    assert not simulator.requests
    assert simulator.get_coil(19) is False


async def test_set_clock(client: A21Client, simulator: A21Simulator) -> None:
    # Tuesday 13 October 2026, 16:05:09
    await client.set_clock(datetime(2026, 10, 13, 16, 5, 9))
    assert simulator.get_holding(61) == 5 << 8 | 9
    assert simulator.get_holding(62) == 16
    assert simulator.get_holding(63) == 13 << 8 | 2
    assert simulator.get_holding(64) == 10 << 8 | 26


async def test_refused_write(client: A21Client, simulator: A21Simulator) -> None:
    del simulator.holdings[74:]
    with pytest.raises(A21RequestRefused) as error:
        await client.set_bypass_mode(BypassMode.OPEN)
    assert error.value.code == 2


async def test_unreachable(client: A21Client, simulator: A21Simulator) -> None:
    await simulator.stop()
    with pytest.raises(A21ConnectionError):
        await client.read_state()
    with pytest.raises(A21ConnectionError):
        await client.turn_on()


async def test_one_connection_at_a_time(
    client: A21Client, simulator: A21Simulator
) -> None:
    """The controller accepts one TCP client: concurrent calls are queued."""
    await asyncio.gather(*(client.read_state() for _ in range(5)), client.set_speed(1))
    assert simulator.refused == 0
    assert simulator.connections == 6


async def test_older_firmware() -> None:
    """Shorter tables are measured once, missing addresses come back as None."""
    simulator = A21Simulator(coils=25, inputs=51, holdings=118)
    await simulator.start()
    try:
        client = A21Client("127.0.0.1", simulator.port)
        state = await client.read_state()
        assert state.ir(50) == 0 and state.ir(51) is None
        assert state.coil(24) is False and state.coil(25) is None
        assert state.hr(117) == 0 and state.hr(118) is None
        assert state.outdoor_temperature == 6.3
        before = len(simulator.requests)
        await client.read_state()
        assert len(simulator.requests) - before == 4
    finally:
        await simulator.stop()
