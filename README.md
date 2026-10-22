# pyventsa21

Async Python library to monitor and control heat recovery ventilation units
fitted with the **VENTS A21** controller, over Modbus TCP.

The A21 controller is found in the ECONOPRIME Connect range sold by
[Econology](https://www.econology.fr/) (Zephyr Connect, DF Connect) and in
other VENTS and Blauberg units.

- No dependency: the Modbus TCP client is built in.
- Local only: the unit is reached on your network, no cloud involved.
- Typed, `asyncio` based.

## Installation

```bash
pip install pyventsa21
```

## Usage

```python
import asyncio

from pyventsa21 import A21Client, OperationMode


async def main() -> None:
    client = A21Client("192.168.1.50")

    state = await client.read_state()
    print(state.is_on, state.speed, state.outdoor_temperature, state.efficiency)
    for alarm in state.alarms:
        print(alarm.code, alarm.severity, alarm.description)

    await client.set_speed(3)
    await client.set_operation_mode(OperationMode.AUTO)


asyncio.run(main())
```

### Connection

By default one TCP connection is kept across calls (`keep_connection=True`);
close it with `await client.close()` or use the client as an async context
manager. With `keep_connection=False` every call opens a short connection
and closes it, the way the manufacturer's tools do. The controller accepts a
single Modbus TCP client per network interface, so concurrent calls on one
`A21Client` are queued.

The Wi-Fi module of the unit sometimes leaks the AT commands of its own
radio chip (`AT+CIPSEND`, `AT+RFPOWER`…) into the Modbus stream. The library
skips that text instead of dropping the connection: closing and reopening at
every leak made the module freeze (firmware 0.43, 2026-10), to the point of
needing a power cycle. TCP keepalive is enabled so a dead peer is noticed
within about a minute. `client.stats` returns counters for bug reports:
connections, connection age, requests, lost answers, stray events and the
latest stray text.

### Identifier and liveness (protocol of the app)

The Modbus table has no serial number. The module also speaks the UDP
protocol of the manufacturer's app (port 4000), read-only here:

```python
from pyventsa21 import async_read_identifier, async_probe

await async_read_identifier("192.168.1.50", "1111")  # "0020003A3032510E"
await async_probe("192.168.1.50", "1111")
# {"identifier": "0020003A3032510E", "device_type": "1", "firmware": "0.43 (28/06/2024)"}
```

`async_probe` is meant for when Modbus stops answering: a module that still
answers here is alive and only its Modbus path is stuck; one silent here too
is frozen and needs a power cycle. Do not send a UDP question while a Modbus
request is in flight: the module answers neither.

### State

`read_state()` returns an `A21State`. Its properties decode the common
values (`is_on`, `operation_mode`, `speed`, the four air temperatures,
`efficiency`, `bypass_position`, `filter_state`, `alarms`, `firmware`…).

The exchanger is described from the four air temperatures:

- `efficiency`: supply-side ratio (supply − outdoor) / (extract − outdoor),
  in percent, `None` when it cannot be measured; `efficiency_status` says
  why (`off`, `bypass`, `heating`, `cooling`, `preheating`, `defrosting`,
  `small_difference`, `no_probe`).
- `efficiency_exhaust_side`: (extract − exhaust) / (extract − outdoor).
  Equal to the supply-side figure with balanced flows.
- `flow_ratio`: apparent extract/supply flow ratio from the heat balance,
  the ratio of the real flows whatever the fan settings; it follows filter
  clogging. 1.0 is balanced.
- `dew_point` of the extract air (from `humidity`, internal or external
  probe) and `condensation_likely` in the exchanger. Condensation releases
  latent heat on the extract side and lowers the exhaust-side figures.
- `defrosting`: the supply fan is stopped while the extract fan runs.

Everything else is available raw, by Modbus address, with the constants of
`pyventsa21.registers`:

```python
from pyventsa21.registers import IR_SUPPLY_RPM, HR_SET_CO2

state.ir(IR_SUPPLY_RPM)  # input register
state.hr(HR_SET_CO2)  # holding register
```

A value is `None` when the firmware does not expose that address: older
firmware has shorter tables, which the library measures once and tolerates.

### Commands

`turn_on`, `turn_off`, `set_operation_mode`, `set_speed`, `set_manual_speed`,
`set_temperature`, `set_bypass_mode`, `set_timer`, `set_schedule`,
`reset_alarms`, `reset_filter_timer`, `set_clock`.

Any other setting can be written with `write_coil` and `write_register`.
Each command returns the state read back from the unit.

Two writes are refused by design: restoring the factory settings and the
password of the engineering menu.

### Errors

- `A21ConnectionError`: the unit cannot be reached or stopped answering.
- `A21RequestRefused`: the unit rejected the request (`code` 2: unknown
  address, 3: value out of range).
- `A21ProtocolError`: the answer is not valid Modbus TCP.

All derive from `A21Error`.

### Alarms

The controller numbers its alarms from 0 to 52. Codes 0 to 45 are described,
with their severity: an `alarm` stops the unit until it is reset, a `warning`
clears by itself.

## Status

Written from the VENTS document "Modbus table for connecting A21 automation
to BMS" (V55-8-1EN-02), tested against a simulator of the controller
(`tests/simulator.py`) and in daily use on an ECONOPRIME DF 350 Connect
(A21 firmware 0.43) through the
[Home Assistant integration](https://github.com/floecono/ha-vents-A21). The
byte order of the multi-byte registers (timers, clock, firmware version)
follows the one documented by [pybls21](https://github.com/jvitkauskas/pybls21)
for the related Blauberg S21 controller.

## Changes

### 0.2.0

- Connection kept across calls by default; stray AT text leaked by the
  Wi-Fi module skipped instead of closing the connection; TCP keepalive;
  `stats` counters; `close()` and async context manager.
- Protocol of the app (UDP 4000, read-only): `async_read_identifier`,
  `async_probe`.
- `A21State`: `efficiency_status`, `efficiency_exhaust_side`, `flow_ratio`,
  `dew_point`, `condensation_likely`, `defrosting`; `humidity` falls back to
  the external probe.

### 0.1.0

- First release.

## Development

```bash
pip install -e ".[test]"
pytest
```

`python tests/simulator.py --port 5020` runs a simulated controller to try an
application without a unit.
