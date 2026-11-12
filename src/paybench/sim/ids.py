"""Deterministic sequential ID factory."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass
class IdFactory:
    """Generate deterministic IDs like cus_000123 from counters."""

    counters: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        n = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = n
        return f"{prefix}_{n:06d}"

    def customer(self) -> str:
        return self.next("cus")

    def account(self) -> str:
        return self.next("acc")

    def card(self) -> str:
        return self.next("crd")

    def merchant(self) -> str:
        return self.next("mch")

    def beneficiary(self) -> str:
        return self.next("ben")

    def payment(self) -> str:
        return self.next("txn")

    def transfer(self) -> str:
        return self.next("trf")

    def refund(self) -> str:
        return self.next("rfd")

    def dispute(self) -> str:
        return self.next("dsp")

    def approval(self) -> str:
        return self.next("apr")

    def message(self) -> str:
        return self.next("msg")

    def snapshot(self) -> IdFactory:
        return deepcopy(self)

    def restore(self, other: IdFactory) -> None:
        self.counters = deepcopy(other.counters)
