"""World: canonical state, hash, snapshot/restore."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import orjson

from paybench.sim.clock import Clock
from paybench.sim.ids import IdFactory
from paybench.sim.ledger import Ledger
from paybench.sim.models import (
    Account,
    Approval,
    Beneficiary,
    Card,
    CaseLogEntry,
    Customer,
    Dispute,
    IdempotencyRecord,
    Merchant,
    Message,
    Payment,
    Refund,
    Transfer,
)
from paybench.sim.rng import Rng


def _canonical_json(obj: Any) -> bytes:
    return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)


@dataclass
class World:
    """Complete simulated payments world state."""

    seed: int
    clock: Clock = field(default_factory=Clock)
    rng: Rng = field(init=False)
    ids: IdFactory = field(default_factory=IdFactory)
    ledger: Ledger = field(default_factory=Ledger)

    customers: dict[str, Customer] = field(default_factory=dict)
    accounts: dict[str, Account] = field(default_factory=dict)
    cards: dict[str, Card] = field(default_factory=dict)
    merchants: dict[str, Merchant] = field(default_factory=dict)
    beneficiaries: dict[str, Beneficiary] = field(default_factory=dict)
    payments: dict[str, Payment] = field(default_factory=dict)
    transfers: dict[str, Transfer] = field(default_factory=dict)
    refunds: dict[str, Refund] = field(default_factory=dict)
    disputes: dict[str, Dispute] = field(default_factory=dict)
    approvals: dict[str, Approval] = field(default_factory=dict)
    messages: list[Message] = field(default_factory=list)
    case_log: list[CaseLogEntry] = field(default_factory=list)
    idempotency: dict[str, IdempotencyRecord] = field(default_factory=dict)

    verified_customers: set[str] = field(default_factory=set)
    session_flags: dict[str, Any] = field(default_factory=dict)
    invariant_violations: list[str] = field(default_factory=list)
    finished: bool = False
    finish_outcome: str | None = None
    finish_summary: str | None = None
    escalated: bool = False
    step: int = 0
    debug_invariants: bool = False
    fx_rates: dict[str, str] = field(default_factory=dict)
    planted: dict[str, Any] = field(default_factory=dict)
    customer_facts: dict[str, str] = field(default_factory=dict)
    fault_plan: Any = None  # FaultPlan | None; typed loosely to avoid cycle

    def __post_init__(self) -> None:
        self.rng = Rng(seed=self.seed)
        if not self.fx_rates:
            self.fx_rates = {
                "USD:INR": "83.50",
                "INR:USD": "0.011976",
                "USD:USD": "1",
                "INR:INR": "1",
            }

    def account_balance(self, account_id: str) -> int:
        acc = self.accounts[account_id]
        return self.ledger.balance(f"customer:{acc.customer_id}", acc.currency)

    def check_invariants(self) -> list[str]:
        """Return invariant violation codes (I1–I5 related)."""
        violations: list[str] = []
        violations.extend(self.ledger.check_i1())

        # I2: no customer balance < 0 unless overdraft
        for acc in self.accounts.values():
            bal = self.ledger.balance(f"customer:{acc.customer_id}", acc.currency)
            # Note: ledger customer accounts may be shared across multi-currency;
            # balance() filters by currency. Negative without overdraft is I2.
            if bal < 0 and not acc.overdraft:
                violations.append(f"I2:{acc.id}:balance={bal}")

        # I3: refunded total <= captured
        for pay in self.payments.values():
            if pay.refunded_amount > pay.amount:
                violations.append(f"I3:{pay.id}:refunded={pay.refunded_amount}>amount={pay.amount}")

        # I4: each idempotency key maps to exactly one effect record
        # (enforced by structure; detect duplicate keys with conflicting hashes)
        seen: dict[str, str] = {}
        for key, rec in self.idempotency.items():
            if key in seen and seen[key] != rec.args_hash:
                violations.append(f"I4:{key}:conflicting")
            seen[key] = rec.args_hash

        # I5: transfer never both completed and reversed without reversing entries
        for tr in self.transfers.values():
            if tr.status.value == "completed":
                # Ensure a debit exists for this transfer
                refs = [e.ref for e in self.ledger.entries if e.ref == tr.id]
                if not refs:
                    violations.append(f"I5:{tr.id}:completed_without_entries")
            if tr.status.value == "reversed":
                # Completed→reversed needs original + :rev entries; pending→reversed may be empty.
                has_original = any(e.ref == tr.id for e in self.ledger.entries)
                has_rev = any(e.ref == f"{tr.id}:rev" for e in self.ledger.entries)
                if has_original and not has_rev:
                    violations.append(f"I5:{tr.id}:reversed_without_rev_entries")

        return violations

    def record_invariant_violations(self) -> None:
        found = self.check_invariants()
        for v in found:
            if v not in self.invariant_violations:
                self.invariant_violations.append(v)

    def to_canonical_dict(self) -> dict[str, Any]:
        """Canonical serializable state (excludes RNG internal, case_log optional)."""
        return {
            "seed": self.seed,
            "clock": self.clock.isoformat(),
            "ids": dict(sorted(self.ids.counters.items())),
            "ledger": self.ledger.to_canonical(),
            "customers": {k: v.model_dump(mode="json") for k, v in sorted(self.customers.items())},
            "accounts": {k: v.model_dump(mode="json") for k, v in sorted(self.accounts.items())},
            "cards": {k: v.model_dump(mode="json") for k, v in sorted(self.cards.items())},
            "merchants": {k: v.model_dump(mode="json") for k, v in sorted(self.merchants.items())},
            "beneficiaries": {
                k: v.model_dump(mode="json") for k, v in sorted(self.beneficiaries.items())
            },
            "payments": {k: v.model_dump(mode="json") for k, v in sorted(self.payments.items())},
            "transfers": {k: v.model_dump(mode="json") for k, v in sorted(self.transfers.items())},
            "refunds": {k: v.model_dump(mode="json") for k, v in sorted(self.refunds.items())},
            "disputes": {k: v.model_dump(mode="json") for k, v in sorted(self.disputes.items())},
            "approvals": {k: v.model_dump(mode="json") for k, v in sorted(self.approvals.items())},
            "messages": [m.model_dump(mode="json") for m in self.messages],
            "idempotency": {
                k: v.model_dump(mode="json") for k, v in sorted(self.idempotency.items())
            },
            "verified_customers": sorted(self.verified_customers),
            "finished": self.finished,
            "finish_outcome": self.finish_outcome,
            "finish_summary": self.finish_summary,
            "escalated": self.escalated,
            "step": self.step,
            "fx_rates": dict(sorted(self.fx_rates.items())),
            "invariant_violations": list(self.invariant_violations),
        }

    def state_hash(self) -> str:
        payload = _canonical_json(self.to_canonical_dict())
        return hashlib.sha256(payload).hexdigest()

    def snapshot(self) -> World:
        return deepcopy(self)

    def restore(self, other: World) -> None:
        snap = deepcopy(other)
        self.seed = snap.seed
        self.clock = snap.clock
        self.rng = snap.rng
        self.ids = snap.ids
        self.ledger = snap.ledger
        self.customers = snap.customers
        self.accounts = snap.accounts
        self.cards = snap.cards
        self.merchants = snap.merchants
        self.beneficiaries = snap.beneficiaries
        self.payments = snap.payments
        self.transfers = snap.transfers
        self.refunds = snap.refunds
        self.disputes = snap.disputes
        self.approvals = snap.approvals
        self.messages = snap.messages
        self.case_log = snap.case_log
        self.idempotency = snap.idempotency
        self.verified_customers = snap.verified_customers
        self.session_flags = snap.session_flags
        self.invariant_violations = snap.invariant_violations
        self.finished = snap.finished
        self.finish_outcome = snap.finish_outcome
        self.finish_summary = snap.finish_summary
        self.escalated = snap.escalated
        self.step = snap.step
        self.debug_invariants = snap.debug_invariants
        self.fx_rates = snap.fx_rates
        self.planted = snap.planted
        self.customer_facts = snap.customer_facts
        self.fault_plan = snap.fault_plan
