"""Fixtures: a simulated A21 controller on a free local port."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest

from pyventsa21 import A21Client

from .simulator import A21Simulator


@pytest.fixture
async def simulator() -> AsyncGenerator[A21Simulator]:
    sim = A21Simulator()
    await sim.start()
    yield sim
    await sim.stop()


@pytest.fixture
def client(simulator: A21Simulator) -> A21Client:
    return A21Client("127.0.0.1", simulator.port)
