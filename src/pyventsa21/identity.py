"""The protocol of the manufacturer's app, for what Modbus does not say.

The Modbus table of the A21 has no serial number. The Wi-Fi module speaks,
besides Modbus TCP, the protocol of the manufacturer's app (UDP port 4000):
a read of parameter 0x7C ("device search") sent with the wildcard
identifier and the password of the unit (the one the app asks for) is
answered with the module's own 16-character identifier, the one the app
shows. Read-only, one datagram, unicast, so it also works across a router.
Checked against a DF 350 Connect (firmware 0.43) on 2026-10-16.

The same channel tells a frozen module from a stuck Modbus path: see
:func:`async_probe`. Nothing here ever writes to the unit.
"""

from __future__ import annotations

import asyncio
import logging
import re

_LOGGER = logging.getLogger(__name__)

APP_PORT = 4000
DEFAULT_DEVICE_PASSWORD = "1111"
_HEADER = b"\xfd\xfd"
_PROTOCOL = 0x02
_WILDCARD = b"DEFAULT_DEVICEID"
_FUNC_READ = 0x01
_FUNC_RESPONSE = 0x06
_PARAM_SEARCH = 0x7C
_PARAM_FIRMWARE = 0x86
_PARAM_DEVICE_TYPE = 0xB9
TIMEOUT = 3.0

_ID_RE = re.compile(r"^[0-9A-Fa-f]{16}$")


def build_read(password: str, params: bytes, device_id: bytes = _WILDCARD) -> bytes:
    """Return the datagram reading the given parameters from a module."""
    pwd = password.encode()
    body = (
        bytes([_PROTOCOL, len(device_id)])
        + device_id
        + bytes([len(pwd)])
        + pwd
        + bytes([_FUNC_READ])
        + params
    )
    return _HEADER + body + (sum(body) & 0xFFFF).to_bytes(2, "little")


def build_search(password: str) -> bytes:
    """Return the datagram asking the module for its identifier."""
    return build_read(password, bytes([_PARAM_SEARCH]))


def parse_answer(answer: bytes) -> tuple[str, dict[int, bytes]] | None:
    """Return (device id, {parameter: value}) from an answer, or None.

    Values are laid out as in the protocol: a parameter byte with a one-byte
    value, FE n in front of an n-byte value, FF x switching the high byte of
    the parameter, FD marking a parameter the module does not know.
    """
    if len(answer) < 8 or answer[:2] != _HEADER:
        return None
    body = answer[2:-2]
    if (sum(body) & 0xFFFF) != int.from_bytes(answer[-2:], "little"):
        return None
    id_size = answer[3]
    device_id = answer[4 : 4 + id_size].decode(errors="replace")
    pos = 4 + id_size
    pos += 1 + answer[pos]  # password
    if pos >= len(answer) or answer[pos] != _FUNC_RESPONSE:
        return None
    data = answer[pos + 1 : -2]
    values: dict[int, bytes] = {}
    pos, high, size = 0, 0, 1
    while pos < len(data):
        marker = data[pos]
        if marker == 0xFF and pos + 1 < len(data):
            high = data[pos + 1]
            pos += 2
            continue
        if marker == 0xFE and pos + 1 < len(data):
            size = data[pos + 1]
            pos += 2
            continue
        if marker == 0xFD and pos + 1 < len(data):
            values[(high << 8) | data[pos + 1]] = b""
            pos += 2
            size = 1
            continue
        values[(high << 8) | marker] = data[pos + 1 : pos + 1 + size]
        pos += 1 + size
        size = 1
    return device_id, values


def parse_identifier(answer: bytes) -> str | None:
    """Return the identifier carried by a search answer, or None."""
    if len(answer) < 8 or answer[:2] != _HEADER:
        return None
    body = answer[2:-2]
    if (sum(body) & 0xFFFF) != int.from_bytes(answer[-2:], "little"):
        return None
    id_size = answer[3]
    device_id = answer[4 : 4 + id_size].decode(errors="replace")
    pos = 4 + id_size
    pos += 1 + answer[pos]  # password
    if pos >= len(answer) or answer[pos] != _FUNC_RESPONSE:
        return None
    if device_id == _WILDCARD.decode() or not _ID_RE.match(device_id):
        return None
    return device_id.upper()


class _Search(asyncio.DatagramProtocol):
    """Keep the first datagram that comes back."""

    def __init__(self) -> None:
        """Prepare the future the answer lands in."""
        self.answer: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Keep the answer."""
        if not self.answer.done():
            self.answer.set_result(data)

    def error_received(self, exc: Exception) -> None:
        """Fail the answer (ICMP unreachable, for instance)."""
        if not self.answer.done():
            self.answer.set_exception(exc)


async def _async_exchange(host: str, port: int, datagram: bytes) -> bytes | None:
    """Send one datagram and return the answer, None on silence."""
    loop = asyncio.get_running_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            _Search, remote_addr=(host, port)
        )
    except OSError as err:
        _LOGGER.debug("Cannot send to %s: %s", host, err)
        return None
    try:
        transport.sendto(datagram)
        async with asyncio.timeout(TIMEOUT):
            return await protocol.answer
    except (TimeoutError, OSError) as err:
        _LOGGER.debug("No answer from %s over UDP: %s", host, err or "silence")
        return None
    finally:
        transport.close()


async def async_read_identifier(
    host: str, password: str = DEFAULT_DEVICE_PASSWORD, port: int = APP_PORT
) -> str | None:
    """Ask the module at host for its identifier; None when it does not say."""
    answer = await _async_exchange(host, port, build_search(password))
    if answer is None:
        return None
    identifier = parse_identifier(answer)
    if identifier is None:
        _LOGGER.debug("Unreadable identifier answer from %s: %s", host, answer.hex())
    return identifier


async def async_probe(
    host: str,
    password: str = DEFAULT_DEVICE_PASSWORD,
    device_id: str | None = None,
    port: int = APP_PORT,
) -> dict[str, str] | None:
    """Ask the module what it still says over the app protocol.

    Used when Modbus no longer answers: a module that answers here is alive
    and only its Modbus path is stuck; one silent here too is frozen.
    Returns the identifier, the device type and the firmware as text, or
    None on silence.
    """
    target = device_id.encode() if device_id else _WILDCARD
    datagram = build_read(
        password, bytes([_PARAM_SEARCH, _PARAM_DEVICE_TYPE, _PARAM_FIRMWARE]), target
    )
    answer = await _async_exchange(host, port, datagram)
    if answer is None:
        return None
    parsed = parse_answer(answer)
    if parsed is None:
        return {"raw": answer.hex()}
    _, values = parsed
    result: dict[str, str] = {}
    if ident := values.get(_PARAM_SEARCH):
        result["identifier"] = ident.decode(errors="replace")
    if kind := values.get(_PARAM_DEVICE_TYPE):
        result["device_type"] = str(int.from_bytes(kind, "little"))
    if fw := values.get(_PARAM_FIRMWARE):
        if len(fw) >= 6:
            year = int.from_bytes(fw[4:6], "little")
            result["firmware"] = f"{fw[0]}.{fw[1]} ({fw[2]:02d}/{fw[3]:02d}/{year})"
        else:
            result["firmware"] = fw.hex()
    return result or {"raw": answer.hex()}
