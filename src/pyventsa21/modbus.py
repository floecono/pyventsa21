"""Minimal asyncio Modbus TCP client.

Self-contained on purpose: the library has no dependency, so it can never
conflict with the Modbus stack an application already uses.

Only the functions the A21 controller needs are implemented
(1, 2, 3, 4, 5, 6).
"""

from __future__ import annotations

import asyncio
import struct

FC_READ_COILS = 0x01
FC_READ_DISCRETE_INPUTS = 0x02
FC_READ_HOLDING_REGISTERS = 0x03
FC_READ_INPUT_REGISTERS = 0x04
FC_WRITE_SINGLE_COIL = 0x05
FC_WRITE_SINGLE_REGISTER = 0x06

EXC_ILLEGAL_FUNCTION = 1
EXC_ILLEGAL_DATA_ADDRESS = 2
EXC_ILLEGAL_DATA_VALUE = 3

_MBAP = struct.Struct(">HHHB")
_MAX_PDU = 253


class A21Error(Exception):
    """Base class for every failure talking to the controller."""


class A21ConnectionError(A21Error):
    """The device could not be reached or stopped answering."""


class A21ProtocolError(A21Error):
    """The device answered with something that is not valid Modbus TCP."""


class A21RequestRefused(A21Error):
    """The controller refused the request with a Modbus exception code.

    code 2 is an address the firmware does not have, code 3 a value outside
    the range the controller accepts.
    """

    def __init__(self, function: int, code: int) -> None:
        """Keep the Modbus function and the exception code."""
        super().__init__(f"Modbus exception {code} on function {function}")
        self.function = function
        self.code = code


class ModbusTcpClient:
    """One Modbus TCP connection. Not safe for concurrent requests."""

    def __init__(
        self, host: str, port: int = 502, unit_id: int = 1, timeout: float = 5.0
    ) -> None:
        """Describe the device to connect to; nothing is opened yet."""
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._transaction = 0

    @property
    def connected(self) -> bool:
        """Return True while the socket is open."""
        return self._writer is not None and not self._writer.is_closing()

    async def connect(self) -> None:
        """Open the TCP connection."""
        if self.connected:
            return
        try:
            async with asyncio.timeout(self.timeout):
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port
                )
        except (OSError, TimeoutError) as err:
            self._reader = self._writer = None
            raise A21ConnectionError(
                f"Cannot connect to {self.host}:{self.port}: {err or type(err).__name__}"
            ) from err

    async def close(self) -> None:
        """Close the TCP connection."""
        writer, self._reader, self._writer = self._writer, None, None
        if writer is None:
            return
        writer.close()
        try:
            async with asyncio.timeout(1):
                await writer.wait_closed()
        except (OSError, TimeoutError):
            pass

    async def _request(self, pdu: bytes) -> bytes:
        """Send one PDU and return the answer PDU."""
        if not self.connected:
            raise A21ConnectionError("Not connected")
        assert self._reader is not None and self._writer is not None

        self._transaction = (self._transaction + 1) & 0xFFFF
        frame = _MBAP.pack(self._transaction, 0, len(pdu) + 1, self.unit_id) + pdu
        try:
            async with asyncio.timeout(self.timeout):
                self._writer.write(frame)
                await self._writer.drain()
                while True:
                    header = await self._reader.readexactly(_MBAP.size)
                    transaction, protocol, length, _unit = _MBAP.unpack(header)
                    if protocol != 0 or not 2 <= length <= _MAX_PDU + 1:
                        raise A21ProtocolError(
                            f"Invalid Modbus TCP header: {header.hex()}"
                        )
                    answer = await self._reader.readexactly(length - 1)
                    # A late answer to a request that timed out earlier would
                    # carry an older transaction id: drop it and keep reading.
                    if transaction == self._transaction:
                        break
        except (OSError, TimeoutError, asyncio.IncompleteReadError) as err:
            await self.close()
            raise A21ConnectionError(
                f"No answer from {self.host}:{self.port}: {err or type(err).__name__}"
            ) from err
        except A21ProtocolError:
            await self.close()
            raise

        function = pdu[0]
        if answer[0] == function | 0x80:
            raise A21RequestRefused(function, answer[1] if len(answer) > 1 else 0)
        if answer[0] != function:
            await self.close()
            raise A21ProtocolError(
                f"Unexpected function {answer[0]} in answer to {function}"
            )
        return answer

    async def _read_bits(self, function: int, address: int, count: int) -> list[bool]:
        answer = await self._request(struct.pack(">BHH", function, address, count))
        payload = answer[2:]
        if len(answer) < 2 or answer[1] != len(payload) or len(payload) * 8 < count:
            await self.close()
            raise A21ProtocolError("Truncated bit answer")
        return [bool(payload[i // 8] >> (i % 8) & 1) for i in range(count)]

    async def _read_registers(
        self, function: int, address: int, count: int
    ) -> list[int]:
        answer = await self._request(struct.pack(">BHH", function, address, count))
        payload = answer[2:]
        if len(answer) < 2 or answer[1] != len(payload) or len(payload) != count * 2:
            await self.close()
            raise A21ProtocolError("Truncated register answer")
        return list(struct.unpack(f">{count}H", payload))

    async def read_coils(self, address: int, count: int) -> list[bool]:
        """Read coils (function 1)."""
        return await self._read_bits(FC_READ_COILS, address, count)

    async def read_discrete_inputs(self, address: int, count: int) -> list[bool]:
        """Read discrete inputs (function 2)."""
        return await self._read_bits(FC_READ_DISCRETE_INPUTS, address, count)

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read holding registers (function 3)."""
        return await self._read_registers(FC_READ_HOLDING_REGISTERS, address, count)

    async def read_input_registers(self, address: int, count: int) -> list[int]:
        """Read input registers (function 4)."""
        return await self._read_registers(FC_READ_INPUT_REGISTERS, address, count)

    async def write_coil(self, address: int, value: bool) -> None:
        """Write one coil (function 5)."""
        await self._request(
            struct.pack(
                ">BHH", FC_WRITE_SINGLE_COIL, address, 0xFF00 if value else 0x0000
            )
        )

    async def write_register(self, address: int, value: int) -> None:
        """Write one holding register (function 6)."""
        await self._request(
            struct.pack(">BHH", FC_WRITE_SINGLE_REGISTER, address, value & 0xFFFF)
        )
