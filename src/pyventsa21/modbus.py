"""Minimal asyncio Modbus TCP client.

Self-contained on purpose: the library has no dependency, so it can never
conflict with the Modbus stack an application already uses.

Only the functions the A21 controller needs are implemented
(1, 2, 3, 4, 5, 6).
"""

from __future__ import annotations

import asyncio
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Any

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
# Stray bytes tolerated in front of an answer before the connection is
# considered lost. The Wi-Fi module of the A21 sometimes leaks the AT
# commands of its controller ("AT+CIPSEND", "AT+RFPOWER"...) into the
# stream; a few dozen bytes at most.
_MAX_STRAY = 256
# TCP keepalive: a dead peer is noticed within about a minute.
_KEEPALIVE_IDLE = 30
_KEEPALIVE_INTERVAL = 10
_KEEPALIVE_COUNT = 3


@dataclass
class ConnectionStats:
    """What happened on the wire, for diagnostics and bug reports."""

    connections: int = 0
    connected_since: float | None = None
    requests: int = 0
    no_answer: int = 0
    stray_events: int = 0
    stray_bytes: int = 0
    last_stray: bytes = field(default=b"", repr=False)

    def as_dict(self) -> dict[str, Any]:
        """Return the counters as plain values."""
        age = (
            None
            if self.connected_since is None
            else round(time.monotonic() - self.connected_since)
        )
        return {
            "connections": self.connections,
            "connection_age_s": age,
            "requests": self.requests,
            "no_answer": self.no_answer,
            "stray_events": self.stray_events,
            "stray_bytes": self.stray_bytes,
            "last_stray": self.last_stray.decode(errors="replace"),
        }


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
        self.stats = ConnectionStats()

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
        self.stats.connections += 1
        self.stats.connected_since = time.monotonic()
        _set_keepalive(self._writer.get_extra_info("socket"))

    async def close(self) -> None:
        """Close the TCP connection."""
        writer, self._reader, self._writer = self._writer, None, None
        self.stats.connected_since = None
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
        self.stats.requests += 1
        frame = _MBAP.pack(self._transaction, 0, len(pdu) + 1, self.unit_id) + pdu
        try:
            async with asyncio.timeout(self.timeout):
                self._writer.write(frame)
                await self._writer.drain()
                while True:
                    header = await self._read_header()
                    transaction, _protocol, length, _unit = _MBAP.unpack(header)
                    answer = await self._reader.readexactly(length - 1)
                    # A late answer to a request that timed out earlier would
                    # carry an older transaction id: drop it and keep reading.
                    if transaction == self._transaction:
                        break
        except (OSError, TimeoutError, asyncio.IncompleteReadError) as err:
            self.stats.no_answer += 1
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

    async def _read_header(self) -> bytes:
        """Return the next MBAP header, skipping stray bytes in front of it.

        The Wi-Fi module occasionally leaks text meant for its own modem
        ("AT+CIPSEND", "AT+RFPOWER") into the Modbus stream. Those bytes
        never form a valid header (protocol id 0, sane length, our unit id,
        a transaction id we have used), so the stream is slid one byte at a
        time until a header fits. Closing the connection on such a leak
        makes the controller redo its fragile modem set-up for nothing.
        """
        assert self._reader is not None
        header = await self._reader.readexactly(_MBAP.size)
        skipped = b""
        while True:
            transaction, protocol, length, unit = _MBAP.unpack(header)
            if (
                protocol == 0
                and 2 <= length <= _MAX_PDU + 1
                and unit == self.unit_id
                and transaction <= self._transaction
            ):
                break
            if len(skipped) >= _MAX_STRAY:
                raise A21ProtocolError(
                    f"No Modbus TCP header in {skipped[:32].hex()}..."
                )
            skipped += header[:1]
            header = header[1:] + await self._reader.readexactly(1)
        if skipped:
            self.stats.stray_events += 1
            self.stats.stray_bytes += len(skipped)
            self.stats.last_stray = skipped
        return header

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


def _set_keepalive(sock: socket.socket | None) -> None:
    """Ask the kernel to probe an idle connection, so a dead peer is noticed."""
    if sock is None:
        return
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        for name, value in (
            ("TCP_KEEPIDLE", _KEEPALIVE_IDLE),
            ("TCP_KEEPINTVL", _KEEPALIVE_INTERVAL),
            ("TCP_KEEPCNT", _KEEPALIVE_COUNT),
        ):
            option = getattr(socket, name, None)
            if option is not None:
                sock.setsockopt(socket.IPPROTO_TCP, option, value)
    except OSError:
        pass
