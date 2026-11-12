"""Metrics and bootstrap CI tests."""

from __future__ import annotations

from paybench.analysis.metrics import bootstrap_ci


def test_bootstrap_ci_is_deterministic() -> None:
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0]
    a = bootstrap_ci(values, seed=99)
    b = bootstrap_ci(values, seed=99)
    c = bootstrap_ci(values, seed=100)
    assert a == b
    assert a != c or values.count(0) == 0
