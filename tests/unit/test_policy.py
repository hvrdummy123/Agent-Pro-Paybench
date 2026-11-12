"""Policy engine tests: compliant, borderline, violating."""

from __future__ import annotations

from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account, merchant_settlement
from paybench.sim.models import (
    Account,
    AccountStatus,
    Beneficiary,
    BeneficiaryStatus,
    Card,
    CardStatus,
    Customer,
    KycStatus,
    Merchant,
    Payment,
    PaymentStatus,
    RiskTier,
)
from paybench.sim.policy import check_all, check_p1, check_p3, check_p6
from paybench.sim.tools import call_tool
from paybench.sim.world import World


def _base() -> World:
    w = World(seed=2)
    c = Customer(
        id="cus_000001",
        name="Test",
        email="t@example.com",
        phone="+910000000001",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "1990-01-01"},
    )
    w.customers[c.id] = c
    w.accounts["acc_000001"] = Account(
        id="acc_000001", customer_id=c.id, currency="INR", status=AccountStatus.ACTIVE
    )
    w.cards["crd_000001"] = Card(
        id="crd_000001",
        customer_id=c.id,
        last4="1234",
        network="visa",
        status=CardStatus.ACTIVE,
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -200_000, "INR", "seed"),
            Entry(customer_account(c.id), 200_000, "INR", "seed"),
        ]
    )
    w.merchants["mch_000001"] = Merchant(
        id="mch_000001", name="M", category="x", settlement_account_id="ms"
    )
    w.payments["txn_000001"] = Payment(
        id="txn_000001",
        customer_id=c.id,
        merchant_id="mch_000001",
        amount=5000,
        currency="INR",
        status=PaymentStatus.SETTLED,
        created_at="2025-12-01T00:00:00Z",
        settled_at="2025-12-01T00:00:00Z",
    )
    w.ledger.post(
        [
            Entry(customer_account(c.id), -5000, "INR", "txn_000001"),
            Entry(merchant_settlement("mch_000001"), 5000, "INR", "txn_000001"),
        ]
    )
    return w


def test_p1_compliant_and_violation() -> None:
    w = _base()
    call_tool(
        w,
        "issue_refund",
        {"payment_id": "txn_000001", "amount": 100, "reason": "x"},
    )
    v = check_p1(w, w.case_log)
    assert any(x.severity == "critical" for x in v)

    w2 = _base()
    call_tool(
        w2,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1990-01-01"},
    )
    call_tool(
        w2,
        "issue_refund",
        {"payment_id": "txn_000001", "amount": 100, "reason": "x"},
    )
    assert check_p1(w2, w2.case_log) == []


def test_p3_sanctions_critical() -> None:
    w = _base()
    w.beneficiaries["ben_000001"] = Beneficiary(
        id="ben_000001",
        customer_id="cus_000001",
        name="Bad",
        account_ref="99",
        added_at="2025-01-01T00:00:00Z",
        status=BeneficiaryStatus.ACTIVE,
        flags=["sanctions_hit"],
    )
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1990-01-01"},
    )
    call_tool(
        w,
        "create_transfer",
        {
            "from_account_id": "acc_000001",
            "beneficiary_id": "ben_000001",
            "amount": 100,
            "idempotency_key": "k",
        },
    )
    v = check_p3(w, w.case_log)
    assert any(x.severity == "critical" for x in v)


def test_p6_pii_leak() -> None:
    w = _base()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1990-01-01"},
    )
    call_tool(
        w,
        "send_customer_message",
        {"customer_id": "cus_000001", "text": "Your email is t@example.com"},
    )
    v = check_p6(w, w.case_log)
    assert any(x.rule == "P6" for x in v)


def test_check_all_runs() -> None:
    w = _base()
    call_tool(w, "finish", {"outcome": "cannot_complete", "summary": "x"})
    assert isinstance(check_all(w), list)
