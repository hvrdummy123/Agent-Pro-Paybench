"""Unit tests for Ledger."""

from __future__ import annotations

import pytest

from paybench.sim.ledger import (
    BANK_FLOAT,
    Entry,
    Ledger,
    LedgerError,
    customer_account,
    merchant_settlement,
)


def test_balanced_posting() -> None:
    led = Ledger()
    led.post(
        [
            Entry(customer_account("cus_1"), -100, "INR", "txn_1"),
            Entry(merchant_settlement("mch_1"), 100, "INR", "txn_1"),
        ]
    )
    assert led.balance(customer_account("cus_1"), "INR") == -100
    assert led.check_i1() == []


def test_unbalanced_rejected() -> None:
    led = Ledger()
    with pytest.raises(LedgerError, match="unbalanced"):
        led.post([Entry(BANK_FLOAT, 50, "INR", "x")])


def test_empty_rejected() -> None:
    led = Ledger()
    with pytest.raises(LedgerError, match="empty"):
        led.post([])


def test_mixed_currency_rejected() -> None:
    led = Ledger()
    with pytest.raises(LedgerError, match="mixed"):
        led.post(
            [
                Entry(BANK_FLOAT, -10, "INR", "x"),
                Entry(customer_account("c"), 10, "USD", "x"),
            ]
        )


def test_snapshot_restore() -> None:
    led = Ledger()
    led.post(
        [
            Entry(BANK_FLOAT, -5, "USD", "a"),
            Entry(customer_account("c"), 5, "USD", "a"),
        ]
    )
    snap = led.snapshot()
    led.post(
        [
            Entry(BANK_FLOAT, -1, "USD", "b"),
            Entry(customer_account("c"), 1, "USD", "b"),
        ]
    )
    assert len(led.entries) == 4
    led.restore(snap)
    assert len(led.entries) == 2
