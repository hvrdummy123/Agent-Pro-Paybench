"""Double-entry ledger with balance invariants."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


class LedgerError(ValueError):
    """Invalid ledger posting."""


@dataclass(frozen=True, slots=True)
class Entry:
    account: str
    amount: int  # signed minor units; positive = credit to this account
    currency: str
    ref: str
    memo: str = ""


@dataclass
class Ledger:
    """Append-only double-entry ledger. Balances are derived, never stored."""

    entries: list[Entry] = field(default_factory=list)

    def post(self, lines: list[Entry]) -> None:
        if not lines:
            raise LedgerError("empty posting")
        currencies = {e.currency for e in lines}
        if len(currencies) != 1:
            raise LedgerError(f"mixed currencies in posting: {currencies}")
        total = sum(e.amount for e in lines)
        if total != 0:
            raise LedgerError(f"unbalanced posting: sum={total}")
        self.entries.extend(lines)

    def balance(self, account: str, currency: str | None = None) -> int:
        total = 0
        for e in self.entries:
            if e.account != account:
                continue
            if currency is not None and e.currency != currency:
                continue
            total += e.amount
        return total

    def balances_by_currency(self) -> dict[str, int]:
        """Sum of all entries per currency (must be 0 for I1)."""
        out: dict[str, int] = {}
        for e in self.entries:
            out[e.currency] = out.get(e.currency, 0) + e.amount
        return out

    def check_i1(self) -> list[str]:
        """I1: sum of all ledger entries per currency == 0."""
        violations: list[str] = []
        for cur, total in sorted(self.balances_by_currency().items()):
            if total != 0:
                violations.append(f"I1:{cur}:sum={total}")
        return violations

    def customer_balance(self, customer_id: str, currency: str) -> int:
        return self.balance(f"customer:{customer_id}", currency)

    def to_canonical(self) -> list[dict[str, Any]]:
        return [
            {
                "account": e.account,
                "amount": e.amount,
                "currency": e.currency,
                "ref": e.ref,
                "memo": e.memo,
            }
            for e in self.entries
        ]

    def snapshot(self) -> Ledger:
        return deepcopy(self)

    def restore(self, other: Ledger) -> None:
        self.entries = deepcopy(other.entries)


def customer_account(customer_id: str) -> str:
    return f"customer:{customer_id}"


def merchant_settlement(merchant_id: str) -> str:
    return f"merchant_settlement:{merchant_id}"


BANK_FLOAT = "bank_float"
FEES = "fees"
SUSPENSE = "suspense"
DISPUTE_HOLD = "dispute_hold"
