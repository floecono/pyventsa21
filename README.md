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

Every call opens a short TCP connection and closes it. The controller accepts
a single Modbus TCP client per network interface, so the library never keeps
the connection; concurrent calls on one `A21Client` are queued.

### State

`read_state()` returns an `A21State`. Its properties decode the common
values (`is_on`, `operation_mode`, `speed`, the four air temperatures,
`efficiency`, `bypass_position`, `filter_state`, `alarms`, `firmware`…).

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
to BMS" (V55-8-1EN-02) and tested against a simulator of the controller
(`tests/simulator.py`). It has not been validated on a real unit yet; the byte
order of the multi-byte registers (timers, clock, firmware version) follows
the one documented by [pybls21](https://github.com/jvitkauskas/pybls21) for
the related Blauberg S21 controller.

## Development

```bash
pip install -e ".[test]"
pytest
```

`python tests/simulator.py --port 5020` runs a simulated controller to try an
application without a unit.
