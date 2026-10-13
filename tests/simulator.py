"""Modbus TCP simulator of an A21 controller, for tests and demos.

Run it standalone to try an application without a real unit:

    python tests/simulator.py --port 5020

then point the application at this computer's IP address and port 5020.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import struct

COILS = 26
DISCRETE = 72
INPUTS = 54
HOLDINGS = 183


def _temp(celsius: float) -> int:
    return round(celsius * 10) & 0xFFFF


def default_coils() -> list[int]:
    coils = [0] * COILS
    coils[0] = 1  # power on
    coils[5] = 1  # main humidity sensor active
    coils[13] = 1  # boost switch input
    coils[14] = 1  # fireplace switch input
    return coils


def default_inputs() -> list[int]:
    ir = [0] * INPUTS
    ir[0] = _temp(21.4)  # selected sensor
    ir[1] = _temp(6.3)  # outdoor
    ir[2] = _temp(19.2)  # supply
    ir[3] = _temp(21.4)  # extract
    ir[4] = _temp(8.9)  # exhaust
    for address in (5, 6, 7, 8):
        ir[address] = 0x8000  # no sensor
    ir[9] = 3012  # RTC battery, mV
    ir[10] = 47  # humidity
    ir[23] = 1480  # supply rpm
    ir[24] = 1455  # extract rpm
    ir[25] = (12 << 8) | 34  # timer: 12 min 34 s
    ir[26] = 1  # timer: 1 h
    ir[27] = (5 << 8) | 42  # filter timer: 5 h 42 min
    ir[28] = 62  # filter timer: 62 days
    ir[29] = (7 << 8) | 15  # motor hours: 7 h 15 min
    ir[30] = 412  # motor hours: 412 days
    ir[31] = 0  # filters clean
    ir[32] = 1
    ir[33] = 23
    ir[34] = (2 << 8) | 15  # firmware 2.15
    ir[35] = (18 << 8) | 4  # 18 April
    ir[36] = 2023
    ir[37] = 1  # A21
    ir[38] = 0  # no alarm
    ir[45] = 0
    ir[51] = 0  # bypass closed
    ir[52] = 70
    ir[53] = 70
    return ir


def default_holdings() -> list[int]:
    hr = [0] * HOLDINGS
    hr[0] = 0  # percent mode
    hr[1] = 3  # three speeds
    hr[2] = 2  # speed 2
    hr[3] = 30
    hr[4] = 100
    hr[5:17] = [0, 0, 40, 40, 70, 70, 100, 100, 100, 100, 100, 100]
    hr[17] = 50
    hr[18] = 50
    hr[19:23] = [100, 100, 60, 40]
    hr[43] = 3  # auto
    hr[44] = 23
    hr[45] = 60
    hr[46] = 1200
    hr[47] = 400
    hr[48] = 40
    hr[49] = 1
    hr[50] = 23
    hr[51] = 30  # timer: 0 h 30 min
    hr[52] = 7
    hr[53] = 2
    hr[56] = 2
    hr[57] = 1  # bypass with two-point control
    hr[58] = 90
    hr[74] = 2  # bypass auto
    hr[75] = 100
    hr[103] = 2
    hr[110] = 0  # the bypass diverts the outdoor air
    hr[124] = (ord("1") << 8) | ord("1")
    hr[125] = (ord("1") << 8) | ord("1")
    return hr


class A21Simulator:
    """An A21 controller listening on TCP, written without any dependency."""

    def __init__(
        self,
        port: int = 0,
        host: str = "127.0.0.1",
        *,
        coils: int = COILS,
        inputs: int = INPUTS,
        holdings: int = HOLDINGS,
        single_client: bool = True,
    ) -> None:
        """Create the simulator.

        coils/inputs/holdings shorten a table to mimic older firmware.
        single_client mimics the real controller, which accepts one TCP
        client at a time.
        """
        self.host = host
        self.port = port
        self.coils = default_coils()[:coils]
        self.discrete = [0] * DISCRETE
        self.inputs = default_inputs()[:inputs]
        self.holdings = default_holdings()[:holdings]
        self.single_client = single_client
        self.connections = 0
        self.refused = 0
        self.requests: list[tuple[int, int, int]] = []
        self._clients: set[asyncio.StreamWriter] = set()
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, self.host, self.port)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        for writer in list(self._clients):
            writer.close()
        await self._server.wait_closed()
        self._server = None

    async def _serve(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if self.single_client and self._clients:
            self.refused += 1
            writer.close()
            return
        self.connections += 1
        self._clients.add(writer)
        try:
            while True:
                header = await reader.readexactly(7)
                transaction, _protocol, length, unit = struct.unpack(">HHHB", header)
                pdu = await reader.readexactly(length - 1)
                answer = self._handle(pdu)
                writer.write(
                    struct.pack(">HHHB", transaction, 0, len(answer) + 1, unit) + answer
                )
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self._clients.discard(writer)
            writer.close()

    def _handle(self, pdu: bytes) -> bytes:
        function = pdu[0]
        if function not in (1, 2, 3, 4, 5, 6) or len(pdu) != 5:
            return bytes([function | 0x80, 1])
        address, value = struct.unpack(">HH", pdu[1:5])
        self.requests.append((function, address, value))
        table = {
            1: self.coils,
            2: self.discrete,
            3: self.holdings,
            4: self.inputs,
            5: self.coils,
            6: self.holdings,
        }[function]

        if function in (1, 2):
            if not 1 <= value <= 2000:
                return bytes([function | 0x80, 3])
            if address + value > len(table):
                return bytes([function | 0x80, 2])
            data = bytearray((value + 7) // 8)
            for index in range(value):
                if table[address + index]:
                    data[index // 8] |= 1 << (index % 8)
            return bytes([function, len(data)]) + bytes(data)

        if function in (3, 4):
            if not 1 <= value <= 125:
                return bytes([function | 0x80, 3])
            if address + value > len(table):
                return bytes([function | 0x80, 2])
            words = table[address : address + value]
            return bytes([function, 2 * value]) + struct.pack(f">{value}H", *words)

        if address >= len(table):
            return bytes([function | 0x80, 2])
        if function == 5:
            if value not in (0x0000, 0xFF00):
                return bytes([function | 0x80, 3])
            table[address] = int(value == 0xFF00)
        else:
            table[address] = value
        return pdu

    def set_coil(self, address: int, value: bool) -> None:
        self.coils[address] = int(value)

    def get_coil(self, address: int) -> bool:
        return bool(self.coils[address])

    def set_discrete(self, address: int, value: bool) -> None:
        self.discrete[address] = int(value)

    def set_holding(self, address: int, value: int) -> None:
        self.holdings[address] = value

    def get_holding(self, address: int) -> int:
        return self.holdings[address]

    def set_input(self, address: int, value: int) -> None:
        self.inputs[address] = value

    def set_temperature(self, address: int, celsius: float) -> None:
        self.inputs[address] = _temp(celsius)


async def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5020)
    args = parser.parse_args()
    simulator = A21Simulator(args.port, args.host)
    await simulator.start()
    print(f"A21 simulator listening on {args.host}:{args.port} - Ctrl+C to stop")
    try:
        await asyncio.Event().wait()
    finally:
        await simulator.stop()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())
