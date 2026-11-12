"""Broader tool coverage: reads, disputes, cards, approvals, control."""

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
from paybench.sim.tools import REGISTRY, call_tool
from paybench.sim.world import World


def _world() -> World:
    w = World(seed=9)
    c = Customer(
        id="cus_000001",
        name="Asha",
        email="asha@example.com",
        phone="+911112223334",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "1992-05-05", "card_last4": "9999"},
    )
    w.customers[c.id] = c
    w.accounts["acc_000001"] = Account(
        id="acc_000001", customer_id=c.id, currency="INR", status=AccountStatus.ACTIVE
    )
    w.cards["crd_000001"] = Card(
        id="crd_000001",
        customer_id=c.id,
        last4="9999",
        network="visa",
        status=CardStatus.ACTIVE,
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -2_000_000, "INR", "seed"),
            Entry(customer_account(c.id), 2_000_000, "INR", "seed"),
        ]
    )
    w.merchants["mch_000001"] = Merchant(
        id="mch_000001",
        name="Shop",
        category="retail",
        settlement_account_id="ms",
        notes="ordinary notes",
    )
    w.payments["txn_000001"] = Payment(
        id="txn_000001",
        customer_id=c.id,
        merchant_id="mch_000001",
        amount=420_000,
        currency="INR",
        status=PaymentStatus.SETTLED,
        created_at="2025-12-15T00:00:00Z",
        settled_at="2025-12-15T00:00:00Z",
        memo="charge",
    )
    w.ledger.post(
        [
            Entry(customer_account(c.id), -420_000, "INR", "txn_000001"),
            Entry(merchant_settlement("mch_000001"), 420_000, "INR", "txn_000001"),
        ]
    )
    w.beneficiaries["ben_000001"] = Beneficiary(
        id="ben_000001",
        customer_id=c.id,
        name="Ben",
        account_ref="22",
        added_at="2025-01-01T00:00:00Z",
        status=BeneficiaryStatus.ACTIVE,
    )
    w.customer_facts = {"dob": "1992-05-05", "card_last4": "9999"}
    return w


def test_registry_has_all_tools() -> None:
    assert len(REGISTRY.tools) == 26


def test_read_and_dispute_flow() -> None:
    w = _world()
    assert call_tool(w, "search_customers", {"query": "asha"})["ok"]
    assert call_tool(w, "get_account", {"account_id": "acc_000001"})["ok"]
    assert call_tool(w, "list_payments", {"customer_id": "cus_000001"})["ok"]
    assert call_tool(w, "get_payment", {"payment_id": "txn_000001"})["ok"]
    assert call_tool(w, "get_merchant", {"merchant_id": "mch_000001"})["ok"]
    assert call_tool(w, "get_fx_rate", {"base": "USD", "quote": "INR"})["ok"]
    assert call_tool(w, "get_policy", {})["ok"]

    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1992-05-05"},
    )
    assert call_tool(w, "freeze_card", {"card_id": "crd_000001", "reason": "fraud"})["ok"]
    assert call_tool(
        w,
        "flag_payment",
        {"payment_id": "txn_000001", "flag": "suspected_fraud"},
    )["ok"]
    d = call_tool(
        w,
        "open_dispute",
        {"payment_id": "txn_000001", "reason_code": "unauthorized"},
    )
    assert d["ok"]
    did = d["data"]["id"]
    assert call_tool(w, "get_dispute", {"dispute_id": did})["ok"]
    assert call_tool(
        w,
        "submit_dispute_evidence",
        {"dispute_id": did, "evidence_type": "note", "content": "not me"},
    )["ok"]
    assert call_tool(w, "unfreeze_card", {"card_id": "crd_000001"})["ok"]
    assert call_tool(
        w,
        "send_customer_message",
        {"customer_id": "cus_000001", "text": "Card ending 9999 frozen then reviewed."},
    )["ok"]
    assert call_tool(w, "ask_customer", {"question": "card last4?"})["ok"]
    assert call_tool(w, "escalate_to_human", {"summary": "need review", "reason": "fraud"})["ok"]
    assert call_tool(w, "finish", {"outcome": "escalated", "summary": "done"})["ok"]


def test_approval_and_wait() -> None:
    w = _world()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1992-05-05"},
    )
    a = call_tool(
        w,
        "request_approval",
        {
            "kind": "refund",
            "subject_id": "txn_000001",
            "amount": 420_000,
            "justification": "customer request",
        },
    )
    assert a["ok"]
    aid = a["data"]["id"]
    pending = call_tool(w, "get_approval", {"approval_id": aid})
    assert pending["data"]["status"] == "pending"
    call_tool(w, "wait", {"seconds": 60})
    done = call_tool(w, "get_approval", {"approval_id": aid})
    assert done["data"]["status"] == "approved"


def test_reverse_transfer_and_list() -> None:
    w = _world()
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1992-05-05"},
    )
    t = call_tool(
        w,
        "create_transfer",
        {
            "from_account_id": "acc_000001",
            "beneficiary_id": "ben_000001",
            "amount": 1000,
            "idempotency_key": "t1",
        },
    )
    assert t["ok"]
    assert call_tool(w, "list_transfers", {"account_id": "acc_000001"})["ok"]
    assert call_tool(
        w,
        "reverse_transfer",
        {"transfer_id": t["data"]["id"], "reason": "mistake", "idempotency_key": "rev1"},
    )["ok"]


def test_unknown_tool() -> None:
    w = _world()
    r = call_tool(w, "nope", {})
    assert not r["ok"] and r["error"]["code"] == "NOT_FOUND"
