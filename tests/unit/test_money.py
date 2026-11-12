"""Unit tests for Money."""

from __future__ import annotations

from decimal import Decimal

import pytest

from paybench.sim.money import Money, MoneyError, convert_fx


def test_add_sub_compare() -> None:
    a = Money(100, "INR")
    b = Money(40, "INR")
    assert (a + b).amount == 140
    assert (a - b).amount == 60
    assert a > b
    assert (-a).amount == -100


def test_currency_mismatch_raises() -> None:
    with pytest.raises(MoneyError, match="currency mismatch"):
        _ = Money(1, "INR") + Money(1, "USD")


def test_no_float_amount() -> None:
    with pytest.raises(MoneyError, match="amount must be int"):
        Money(1.5, "INR")  # type: ignore[arg-type]


def test_no_bool_amount() -> None:
    with pytest.raises(MoneyError, match="amount must be int"):
        Money(True, "INR")  # type: ignore[arg-type]


def test_currency_normalized() -> None:
    assert Money(1, "inr").currency == "INR"


def test_fx_rounding_half_even() -> None:
    # 100 * 1.005 = 100.5 → banker's round to 100 (even)
    m = convert_fx(Money(100, "USD"), "INR", Decimal("1.005"))
    assert m.amount == 100
    assert m.currency == "INR"
    # 101 * 1.005 = 101.505 → rounds to 102? 101.505 → nearest even...
    # Actually 101.505 to_integral ROUND_HALF_EVEN: 101.5 would go to 102 (even? 102 is even)
    # 101.505 is closer to 102 than half-even at .5; let's use exact .5
    m2 = convert_fx(Money(101, "USD"), "INR", Decimal("1.005"))
    # 101 * 1.005 = 101.505 → rounds away from half; nearest is 102
    assert m2.amount == 102


def test_fx_rejects_float_rate() -> None:
    with pytest.raises(MoneyError, match="must not be float"):
        convert_fx(Money(100, "USD"), "INR", 83.5)  # type: ignore[arg-type]


def test_same_currency_fx_noop() -> None:
    m = Money(50, "USD")
    assert convert_fx(m, "USD", "1") is m or convert_fx(m, "USD", "1").amount == 50


def test_mul() -> None:
    assert (Money(10, "USD") * 3).amount == 30
    with pytest.raises(MoneyError):
        _ = Money(10, "USD") * 2.5  # type: ignore[operator]
