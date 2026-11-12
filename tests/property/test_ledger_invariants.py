"""Property: ledger invariants hold under random valid tool sequences."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account, merchant_settlement
from paybench.sim.models import (
    Account,
    AccountStatus,
    Beneficiary,
    BeneficiaryStatus,
    Customer,
    KycStatus,
    Merchant,
    Payment,
    PaymentStatus,
    RiskTier,
)
from paybench.sim.tools import call_tool
from paybench.sim.world import World


def _world(seed: int) -> World:
    w = World(seed=seed)
    c = Customer(
        id="cus_000001",
        name="Prop",
        email="p@example.com",
        phone="+910000000099",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "1991-02-02"},
    )
    w.customers[c.id] = c
    w.accounts["acc_000001"] = Account(
        id="acc_000001", customer_id=c.id, currency="INR", status=AccountStatus.ACTIVE
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -500_000, "INR", "seed"),
            Entry(customer_account(c.id), 500_000, "INR", "seed"),
        ]
    )
    w.merchants["mch_000001"] = Merchant(
        id="mch_000001", name="M", category="x", settlement_account_id="ms"
    )
    for i in range(3):
        pid = f"txn_{i + 1:06d}"
        amt = 10_000 * (i + 1)
        w.payments[pid] = Payment(
            id=pid,
            customer_id=c.id,
            merchant_id="mch_000001",
            amount=amt,
            currency="INR",
            status=PaymentStatus.SETTLED,
            created_at="2025-12-01T00:00:00Z",
            settled_at="2025-12-01T00:00:00Z",
        )
        w.ledger.post(
            [
                Entry(customer_account(c.id), -amt, "INR", pid),
                Entry(merchant_settlement("mch_000001"), amt, "INR", pid),
            ]
        )
    w.beneficiaries["ben_000001"] = Beneficiary(
        id="ben_000001",
        customer_id=c.id,
        name="Ben",
        account_ref="1",
        added_at="2025-01-01T00:00:00Z",
        status=BeneficiaryStatus.ACTIVE,
    )
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1991-02-02"},
    )
    return w


@given(seed=st.integers(0, 200), n=st.integers(1, 8))
@settings(max_examples=40)
def test_invariants_under_refunds_and_transfers(seed: int, n: int) -> None:
    w = _world(seed)
    rng = w.rng.child("prop")
    for i in range(n):
        if rng.random() < 0.5:
            pid = rng.choice(sorted(w.payments))
            pay = w.payments[pid]
            rem = pay.amount - pay.refunded_amount
            if rem > 0:
                amt = rng.randint(1, rem)
                call_tool(
                    w,
                    "issue_refund",
                    {
                        "payment_id": pid,
                        "amount": amt,
                        "reason": "prop",
                        "idempotency_key": f"r-{i}",
                    },
                )
        else:
            bal = w.account_balance("acc_000001")
            if bal > 100:
                amt = rng.randint(1, min(1000, bal))
                call_tool(
                    w,
                    "create_transfer",
                    {
                        "from_account_id": "acc_000001",
                        "beneficiary_id": "ben_000001",
                        "amount": amt,
                        "idempotency_key": f"t-{i}",
                    },
                )
    assert w.check_invariants() == []
