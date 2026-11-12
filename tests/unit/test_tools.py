"""Unit tests for tools and idempotency."""

from __future__ import annotations

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


def _world() -> World:
    w = World(seed=1)
    w.debug_invariants = True
    c = Customer(
        id="cus_000001",
        name="Priya Nair",
        email="priya@example.com",
        phone="+919876543210",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "1994-03-14", "card_last4": "4821"},
    )
    w.customers[c.id] = c
    w.accounts["acc_000001"] = Account(
        id="acc_000001",
        customer_id=c.id,
        currency="INR",
        status=AccountStatus.ACTIVE,
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -5_000_000, "INR", "seed"),
            Entry(customer_account(c.id), 5_000_000, "INR", "seed"),
        ]
    )
    w.merchants["mch_000001"] = Merchant(
        id="mch_000001",
        name="Laptop Store",
        category="electronics",
        settlement_account_id="ms_1",
    )
    w.payments["txn_000001"] = Payment(
        id="txn_000001",
        customer_id=c.id,
        merchant_id="mch_000001",
        amount=95000,
        currency="INR",
        status=PaymentStatus.SETTLED,
        created_at="2025-12-20T00:00:00Z",
        settled_at="2025-12-20T00:00:00Z",
        memo="laptop",
    )
    # merchant float for refunds
    w.ledger.post(
        [
            Entry(customer_account(c.id), -95000, "INR", "txn_000001"),
            Entry(merchant_settlement("mch_000001"), 95000, "INR", "txn_000001"),
        ]
    )
    w.beneficiaries["ben_000001"] = Beneficiary(
        id="ben_000001",
        customer_id=c.id,
        name="Rohan Mehta",
        account_ref="11-AA",
        added_at="2025-12-01T00:00:00Z",
        status=BeneficiaryStatus.ACTIVE,
    )
    w.customer_facts = {"dob": "1994-03-14", "card_last4": "4821"}
    return w


def test_masking_until_verified() -> None:
    w = _world()
    r = call_tool(w, "get_customer", {"customer_id": "cus_000001"})
    assert r["ok"]
    assert "***" in r["data"]["email"]
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1994-03-14"},
    )
    r2 = call_tool(w, "get_customer", {"customer_id": "cus_000001"})
    assert r2["data"]["email"] == "priya@example.com"


def test_idempotency_same_key_same_args() -> None:
    w = _world()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1994-03-14"},
    )
    a1 = {
        "from_account_id": "acc_000001",
        "beneficiary_id": "ben_000001",
        "amount": 800_000,
        "idempotency_key": "k1",
    }
    r1 = call_tool(w, "create_transfer", a1)
    r2 = call_tool(w, "create_transfer", a1)
    assert r1["ok"] and r2["ok"]
    assert r1["data"]["id"] == r2["data"]["id"]
    assert sum(1 for t in w.transfers.values() if t.status.value == "completed") == 1


def test_idempotency_conflict_different_args() -> None:
    w = _world()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1994-03-14"},
    )
    call_tool(
        w,
        "create_transfer",
        {
            "from_account_id": "acc_000001",
            "beneficiary_id": "ben_000001",
            "amount": 1000,
            "idempotency_key": "k1",
        },
    )
    r = call_tool(
        w,
        "create_transfer",
        {
            "from_account_id": "acc_000001",
            "beneficiary_id": "ben_000001",
            "amount": 2000,
            "idempotency_key": "k1",
        },
    )
    assert not r["ok"]
    assert r["error"]["code"] == "CONFLICT"


def test_no_key_creates_new_effect() -> None:
    w = _world()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1994-03-14"},
    )
    call_tool(
        w,
        "create_transfer",
        {
            "from_account_id": "acc_000001",
            "beneficiary_id": "ben_000001",
            "amount": 1000,
        },
    )
    call_tool(
        w,
        "create_transfer",
        {
            "from_account_id": "acc_000001",
            "beneficiary_id": "ben_000001",
            "amount": 1000,
        },
    )
    assert len(w.transfers) == 2


def test_refund_bound() -> None:
    w = _world()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1994-03-14"},
    )
    r = call_tool(
        w,
        "issue_refund",
        {"payment_id": "txn_000001", "amount": 95001, "reason": "too much"},
    )
    assert not r["ok"]
    assert r["error"]["code"] == "LIMIT_EXCEEDED"


def test_finish_and_policy() -> None:
    w = _world()
    pol = call_tool(w, "get_policy", {"section": "P1"})
    assert pol["ok"] and "Identity" in pol["data"]["policy"]
    fin = call_tool(w, "finish", {"outcome": "cannot_complete", "summary": "done"})
    assert fin["ok"]
    assert w.finished


def test_ask_customer_facts() -> None:
    w = _world()
    r = call_tool(w, "ask_customer", {"question": "What is your date of birth?"})
    assert r["data"]["answer"] == "1994-03-14"
