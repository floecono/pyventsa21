"""The protocol of the app: identifier and liveness of the Wi-Fi module."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest

from pyventsa21 import async_probe, async_read_identifier, identity
from pyventsa21.identity import build_read, build_search, parse_answer, parse_identifier

# Frame of the vents-breezy library's search, and an answer shaped like the
# one a DF 350 Connect gave on 2026-10-16 (identifier in the header and in
# parameter 0x7C, a 2-byte parameter 0xB9 before it).
SEARCH = bytes.fromhex("fdfd021044454641554c545f44455649434549440431313131017cf805")
_BODY = (
    bytes.fromhex("0210")
    + b"0020003A3032510E"
    + bytes.fromhex("0431313131")
    + bytes.fromhex("06fe02b90100fe107c")
    + b"0020003A3032510E"
)
ANSWER = b"\xfd\xfd" + _BODY + (sum(_BODY) & 0xFFFF).to_bytes(2, "little")

# Answer to a probe (0x7C, 0xB9, 0x86): identifier, device type 1, firmware
# 0.43 of 28/06/2024, as the DF 350 answered on 2026-10-20.
_PROBE_BODY = (
    bytes.fromhex("0210")
    + b"0020003A3032510E"
    + bytes.fromhex("0431313131")
    + bytes.fromhex("06fe107c")
    + b"0020003A3032510E"
    + bytes.fromhex("fe02b90100")
    + bytes.fromhex("fe0686002b1c06e807")
)
PROBE_ANSWER = (
    b"\xfd\xfd" + _PROBE_BODY + (sum(_PROBE_BODY) & 0xFFFF).to_bytes(2, "little")
)


def test_search_frame_matches_the_library() -> None:
    assert build_search("1111") == SEARCH


def test_read_frame_addresses_a_module() -> None:
    frame = build_read("1111", bytes([0x7C]), b"0020003A3032510E")
    assert frame[2:4] == b"\x02\x10" and frame[4:20] == b"0020003A3032510E"
    assert frame[-2:] == (sum(frame[2:-2]) & 0xFFFF).to_bytes(2, "little")


def test_answer_is_parsed() -> None:
    assert parse_identifier(ANSWER) == "0020003A3032510E"
    assert parse_identifier(b"\x00\x01") is None
    assert parse_identifier(ANSWER[:-1] + b"\x00") is None  # bad checksum
    assert parse_identifier(SEARCH) is None  # a question, not an answer
    parsed = parse_answer(PROBE_ANSWER)
    assert parsed is not None
    device_id, values = parsed
    assert device_id == "0020003A3032510E"
    assert values[0x7C] == b"0020003A3032510E"
    assert values[0xB9] == b"\x01\x00"
    assert values[0x86] == bytes.fromhex("002b1c06e807")


class _Module(asyncio.DatagramProtocol):
    """A Wi-Fi module answering the search and the probe."""

    def __init__(self) -> None:
        self.received: list[bytes] = []
        self.silent = False

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.received.append(data)
        if self.silent or b"1111" not in data:
            return
        answer = ANSWER if data == SEARCH else PROBE_ANSWER
        self.transport.sendto(answer, addr)  # type: ignore[attr-defined]


@pytest.fixture
async def module(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[tuple[_Module, int]]:
    monkeypatch.setattr(identity, "TIMEOUT", 0.2)
    loop = asyncio.get_running_loop()
    transport, module = await loop.create_datagram_endpoint(
        _Module, local_addr=("127.0.0.1", 0)
    )
    try:
        yield module, transport.get_extra_info("sockname")[1]
    finally:
        transport.close()


async def test_identifier_read_from_the_module(module: tuple[_Module, int]) -> None:
    unit, port = module
    assert await async_read_identifier("127.0.0.1", "1111", port) == "0020003A3032510E"
    assert unit.received == [SEARCH]
    # Wrong password: the module stays silent, the caller goes on without.
    assert await async_read_identifier("127.0.0.1", "0000", port) is None


async def test_probe(module: tuple[_Module, int]) -> None:
    unit, port = module
    assert await async_probe("127.0.0.1", "1111", "0020003A3032510E", port) == {
        "identifier": "0020003A3032510E",
        "device_type": "1",
        "firmware": "0.43 (28/06/2024)",
    }
    assert unit.received[-1][4:20] == b"0020003A3032510E"
    unit.silent = True
    assert await async_probe("127.0.0.1", "1111", None, port) is None
