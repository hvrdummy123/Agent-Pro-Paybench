"""Error-path coverage for tools."""

from __future__ import annotations

from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account
from paybench.sim.models import (
    Account,
    AccountStatus,
    Customer,
    KycStatus,
    RiskTier,
)
from paybench.sim.tools import call_tool
from paybench.sim.tools.base import mask_email, mask_phone
from paybench.sim.world import World


def test_masks_and_not_found() -> None:
    assert mask_email("a@b.co") == "*@b.co"
    assert "***" in mask_email("ada@b.co")
    assert mask_phone("12") == "***"
    w = World(seed=1)
    w.customers["cus_000001"] = Customer(
        id="cus_000001",
        name="N",
        email="n@example.com",
        phone="+911234567890",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "2000-01-01"},
    )
    w.accounts["acc_000001"] = Account(
        id="acc_000001",
        customer_id="cus_000001",
        currency="INR",
        status=AccountStatus.ACTIVE,
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -1000, "INR", "s"),
            Entry(customer_account("cus_000001"), 1000, "INR", "s"),
        ]
    )
    assert not call_tool(w, "get_customer", {"customer_id": "nope"})["ok"]
    assert not call_tool(w, "get_account", {"account_id": "nope"})["ok"]
    assert not call_tool(w, "get_payment", {"payment_id": "nope"})["ok"]
    assert not call_tool(w, "get_merchant", {"merchant_id": "nope"})["ok"]
    assert not call_tool(w, "get_dispute", {"dispute_id": "nope"})["ok"]
    assert not call_tool(w, "get_fx_rate", {"base": "EUR", "quote": "JPY"})["ok"]
    assert not call_tool(w, "search_customers", {"query": ""})["ok"]
    assert not call_tool(w, "list_payments", {"customer_id": "nope"})["ok"]
    assert not call_tool(w, "list_transfers", {"account_id": "nope"})["ok"]
    assert not call_tool(w, "wait", {"seconds": -1})["ok"]
    assert not call_tool(w, "finish", {"outcome": "nope", "summary": "x"})["ok"]
    assert not call_tool(w, "freeze_card", {"card_id": "nope", "reason": "x"})["ok"]
    assert not call_tool(w, "unfreeze_card", {"card_id": "nope"})["ok"]
    assert not call_tool(
        w,
        "verify_customer",
        {"customer_id": "nope", "factor": "dob", "value": "x"},
    )["ok"]
    bad = call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "wrong"},
    )
    assert not bad["ok"]
