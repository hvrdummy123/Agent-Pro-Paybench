"""Unit tests for Rng sub-streams."""

from __future__ import annotations

from paybench.sim.rng import Rng


def test_substreams_independent() -> None:
    r = Rng(seed=42)
    a1 = r.child("a").randint(0, 10_000)
    b1 = r.child("b").randint(0, 10_000)

    r2 = Rng(seed=42)
    # Extra draws on child a must not change child b
    _ = [r2.child("a").random() for _ in range(20)]
    b2 = r2.child("b").randint(0, 10_000)
    assert b1 == b2

    r3 = Rng(seed=42)
    a3 = r3.child("a").randint(0, 10_000)
    assert a1 == a3


def test_same_seed_same_draws() -> None:
    r1 = Rng(7)
    r2 = Rng(7)
    assert [r1.randint(0, 100) for _ in range(10)] == [r2.randint(0, 100) for _ in range(10)]


def test_snapshot_restore() -> None:
    r = Rng(99)
    snap = r.snapshot()
    first = [r.randint(0, 1000) for _ in range(5)]
    r.restore(snap)
    second = [r.randint(0, 1000) for _ in range(5)]
    assert first == second


def test_lognormal_int_clamped() -> None:
    r = Rng(1)
    for _ in range(50):
        v = r.lognormal_int(8.0, 1.0, minimum=100, maximum=500)
        assert 100 <= v <= 500
