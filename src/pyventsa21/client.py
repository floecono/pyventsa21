"""Read and write an A21 controller over Modbus TCP."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from .modbus import (
    EXC_ILLEGAL_DATA_ADDRESS,
    A21ConnectionError,
    A21RequestRefused,
    ModbusTcpClient,
)
from .registers import (
    CL_POWER,
    CL_RESET_ALARM,
    CL_RESET_FILTER_TIMER,
    CL_RESTORE_FACTORY,
    CL_TIMER,
    CL_WEEK,
    COIL_COUNT,
    DEVICE_TYPE_A21,
    DISCRETE_COUNT,
    HOLDING_COUNT,
    HR_BYPASS_MODE,
    HR_ENGINEER_PASSWORD,
    HR_MANUAL_SPEED,
    HR_OPERATION_MODE,
    HR_RTC_DAY_WEEKDAY,
    HR_RTC_HOURS,
    HR_RTC_MIN_SEC,
    HR_RTC_MONTH_YEAR,
    HR_SET_TEMP,
    HR_SPEED_MODE,
    INPUT_COUNT,
    IR_DEVICE_TYPE,
    SPEED_MANUAL,
)
from .state import A21State, BypassMode, OperationMode

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

# Time the controller gets to apply a write before the state is read back.
_SETTLE_DELAY = 0.3
# The controller accepts a single TCP client; right after a disconnection it
# can refuse the next connection for a moment.
_CONNECT_RETRY_DELAY = 0.6


@dataclass(frozen=True, slots=True)
class CoilWrite:
    """Write one coil."""

    address: int
    value: bool


@dataclass(frozen=True, slots=True)
class RegisterWrite:
    """Write one holding register."""

    address: int
    value: int


Write = CoilWrite | RegisterWrite


def _check(write: Write) -> None:
    """Refuse the two writes no application should ever send."""
    if isinstance(write, CoilWrite):
        if write.address == CL_RESTORE_FACTORY:
            raise ValueError("Restoring the factory settings is not supported")
    elif write.address >= HR_ENGINEER_PASSWORD:
        raise ValueError(f"Holding register {write.address} is not writable")


class A21Client:
    """Serialised access to one A21 controller.

    Each call opens its own short TCP connection. The controller only accepts
    one client per network interface and long-lived connections are known to
    go stale, so the socket is never kept between calls. Calls made
    concurrently are queued.

    Every method raises ``A21ConnectionError`` when the unit cannot be
    reached, and ``A21RequestRefused`` when it rejects a value.
    """

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        unit_id: int = DEFAULT_UNIT_ID,
        *,
        timeout: float = 5.0,
    ) -> None:
        """Describe the unit to talk to; nothing is sent yet."""
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._modbus = ModbusTcpClient(host, port, unit_id, timeout)
        self._lock = asyncio.Lock()
        # Number of readable addresses per table, learnt on older firmware.
        self._limits: dict[str, int] = {}

    # --- reading ------------------------------------------------------------
    async def identify(self) -> int:
        """Return the controller type register (1 for an A21)."""
        async with self._lock:
            await self._connect()
            try:
                return (await self._modbus.read_input_registers(IR_DEVICE_TYPE, 1))[0]
            finally:
                await self._modbus.close()

    async def is_a21(self) -> bool:
        """Return True when an A21 controller answers at this address."""
        return await self.identify() == DEVICE_TYPE_A21

    async def read_state(self) -> A21State:
        """Read the four Modbus tables."""
        async with self._lock:
            await self._connect()
            try:
                return await self._read_all()
            finally:
                await self._modbus.close()

    # --- writing ------------------------------------------------------------
    async def write(self, *writes: Write) -> A21State:
        """Apply writes in order, then return the state read back."""
        for write in writes:
            _check(write)
        async with self._lock:
            await self._connect()
            try:
                for write in writes:
                    if isinstance(write, CoilWrite):
                        await self._modbus.write_coil(write.address, write.value)
                    else:
                        await self._modbus.write_register(write.address, write.value)
                await asyncio.sleep(_SETTLE_DELAY)
                return await self._read_all()
            finally:
                await self._modbus.close()

    async def write_coil(self, address: int, value: bool) -> A21State:
        """Write one coil, then return the state read back."""
        return await self.write(CoilWrite(address, value))

    async def write_register(self, address: int, value: int) -> A21State:
        """Write one holding register, then return the state read back."""
        return await self.write(RegisterWrite(address, value))

    async def turn_on(self) -> A21State:
        """Switch the unit on."""
        return await self.write_coil(CL_POWER, True)

    async def turn_off(self) -> A21State:
        """Switch the unit off."""
        return await self.write_coil(CL_POWER, False)

    async def set_operation_mode(self, mode: OperationMode) -> A21State:
        """Select ventilation only, heating, cooling or automatic."""
        return await self.write_register(HR_OPERATION_MODE, int(mode))

    async def set_speed(self, speed: int) -> A21State:
        """Select a preset speed, 1 to 5 (most units have three)."""
        if not 1 <= speed <= 5:
            raise ValueError("speed must be between 1 and 5")
        return await self.write_register(HR_SPEED_MODE, speed)

    async def set_manual_speed(self, percent: int | None = None) -> A21State:
        """Switch to manual speed, optionally setting its percentage first."""
        writes: list[Write] = []
        if percent is not None:
            if not 0 <= percent <= 100:
                raise ValueError("percent must be between 0 and 100")
            writes.append(RegisterWrite(HR_MANUAL_SPEED, percent))
        writes.append(RegisterWrite(HR_SPEED_MODE, SPEED_MANUAL))
        return await self.write(*writes)

    async def set_temperature(self, celsius: int) -> A21State:
        """Set the temperature setpoint, 15 to 30 °C."""
        if not 15 <= celsius <= 30:
            raise ValueError("celsius must be between 15 and 30")
        return await self.write_register(HR_SET_TEMP, celsius)

    async def set_bypass_mode(self, mode: BypassMode) -> A21State:
        """Force the bypass closed or open, or leave it automatic."""
        return await self.write_register(HR_BYPASS_MODE, int(mode))

    async def set_timer(self, on: bool) -> A21State:
        """Start or stop the main timer."""
        return await self.write_coil(CL_TIMER, on)

    async def set_schedule(self, on: bool) -> A21State:
        """Enable or disable the weekly schedule."""
        return await self.write_coil(CL_WEEK, on)

    async def reset_alarms(self) -> A21State:
        """Reset the alarms that stopped the unit."""
        return await self.write_coil(CL_RESET_ALARM, True)

    async def reset_filter_timer(self) -> A21State:
        """Restart the filter replacement countdown."""
        return await self.write_coil(CL_RESET_FILTER_TIMER, True)

    async def set_clock(self, now: datetime) -> A21State:
        """Set the clock of the controller to a local date and time."""
        return await self.write(
            RegisterWrite(HR_RTC_MIN_SEC, now.minute << 8 | now.second),
            RegisterWrite(HR_RTC_HOURS, now.hour),
            RegisterWrite(HR_RTC_DAY_WEEKDAY, now.day << 8 | now.isoweekday()),
            RegisterWrite(HR_RTC_MONTH_YEAR, now.month << 8 | now.year % 100),
        )

    # --- internals ----------------------------------------------------------
    async def _connect(self) -> None:
        try:
            await self._modbus.connect()
        except A21ConnectionError:
            await asyncio.sleep(_CONNECT_RETRY_DELAY)
            await self._modbus.connect()

    async def _read_all(self) -> A21State:
        modbus = self._modbus
        return A21State(
            coils=await self._read_table("coils", modbus.read_coils, COIL_COUNT),
            discrete=await self._read_table(
                "discrete inputs", modbus.read_discrete_inputs, DISCRETE_COUNT
            ),
            inputs=await self._read_table(
                "input registers", modbus.read_input_registers, INPUT_COUNT
            ),
            holdings=await self._read_table(
                "holding registers", modbus.read_holding_registers, HOLDING_COUNT
            ),
        )

    async def _read_table[T](
        self,
        name: str,
        reader: Callable[[int, int], Awaitable[list[T]]],
        count: int,
    ) -> list[T | None]:
        """Read addresses 0..count-1, tolerating firmware with a shorter table.

        Older firmware answers "illegal data address" when a request reaches
        past the end of its table. The readable length is then searched once
        and remembered; missing addresses are returned as None.
        """
        limit = self._limits.get(name, count)
        values: list[T] = []
        if limit:
            try:
                values = await reader(0, limit)
            except A21RequestRefused as err:
                if err.code != EXC_ILLEGAL_DATA_ADDRESS:
                    raise
                limit = await self._probe_limit(reader, limit)
                self._limits[name] = limit
                _LOGGER.info(
                    "%s: this firmware exposes %d of %d %s",
                    self.host,
                    limit,
                    count,
                    name,
                )
                values = await reader(0, limit) if limit else []
        return [*values, *([None] * (count - len(values)))]

    @staticmethod
    async def _probe_limit[T](
        reader: Callable[[int, int], Awaitable[list[T]]], failing: int
    ) -> int:
        """Return the largest readable count below a count known to fail."""
        low, high = 0, failing
        while high - low > 1:
            middle = (low + high) // 2
            try:
                await reader(0, middle)
            except A21RequestRefused as err:
                if err.code != EXC_ILLEGAL_DATA_ADDRESS:
                    raise
                high = middle
            else:
                low = middle
        return low
