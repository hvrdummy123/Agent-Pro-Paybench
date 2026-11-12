"""Unit tests for Clock."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paybench.config import EPOCH, MAX_WAIT_S
from paybench.sim.clock import Clock


def test_starts_at_epoch() -> None:
    c = Clock()
    assert c.now == EPOCH


def test_advance_and_wait() -> None:
    c = Clock()
    c.advance(2)
    assert c.now == EPOCH.replace(second=2) or c.seconds_since_epoch() == 2
    c.wait(10)
    assert c.seconds_since_epoch() == 12


def test_wait_bounds() -> None:
    c = Clock()
    with pytest.raises(ValueError):
        c.wait(-1)
    with pytest.raises(ValueError):
        c.wait(MAX_WAIT_S + 1)


def test_negative_advance_raises() -> None:
    c = Clock()
    with pytest.raises(ValueError):
        c.advance(-5)


def test_day_start_and_isoformat() -> None:
    c = Clock()
    c.advance(3600 * 26)  # next day + 2h
    assert c.day_start() == datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    assert c.isoformat().endswith("Z")


def test_snapshot_restore() -> None:
    c = Clock()
    c.advance(100)
    snap = c.snapshot()
    c.advance(50)
    assert c.seconds_since_epoch() == 150
    c.restore(snap)
    assert c.seconds_since_epoch() == 100
