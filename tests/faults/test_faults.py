"""Fault injection semantics tests."""

from __future__ import annotations

from paybench.sim.faults import FaultRule, FaultType, build_fault_plan
from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account
from paybench.sim.models import (
    Account,
    AccountStatus,
    Beneficiary,
    BeneficiaryStatus,
    Customer,
    KycStatus,
    RiskTier,
)
from paybench.sim.tools import call_tool
from paybench.sim.world import World


def _world(seed: int = 1) -> World:
    w = World(seed=seed)
    c = Customer(
        id="cus_000001",
        name="Priya",
        email="p@example.com",
        phone="+910000000001",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "1994-03-14"},
    )
    w.customers[c.id] = c
    w.accounts["acc_000001"] = Account(
        id="acc_000001", customer_id=c.id, currency="INR", status=AccountStatus.ACTIVE
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -5_000_000, "INR", "seed"),
            Entry(customer_account(c.id), 5_000_000, "INR", "seed"),
        ]
    )
    w.beneficiaries["ben_000001"] = Beneficiary(
        id="ben_000001",
        customer_id=c.id,
        name="Rohan Mehta",
        account_ref="11-AA",
        added_at="2025-01-01T00:00:00Z",
        status=BeneficiaryStatus.ACTIVE,
    )
    call_tool(
        w,
        "verify_customer",
        {"customer_id": "cus_000001", "factor": "dob", "value": "1994-03-14"},
    )
    return w


def _transfer_args(key: str | None = "k1") -> dict:
    a: dict = {
        "from_account_id": "acc_000001",
        "beneficiary_id": "ben_000001",
        "amount": 800_000,
    }
    if key is not None:
        a["idempotency_key"] = key
    return a


def test_timeout_after_commit_with_key() -> None:
    w = _world()
    w.fault_plan = build_fault_plan(
        seed=1,
        profile="clean",
        targeted=[
            FaultRule(
                fault_type=FaultType.TIMEOUT_AFTER_COMMIT,
                tool="create_transfer",
                nth_call=1,
            )
        ],
    )
    r1 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert not r1["ok"]
    assert r1["error"]["code"] == "TIMEOUT"
    assert len(w.transfers) == 1
    r2 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert r2["ok"]
    assert r2["data"]["id"] == next(iter(w.transfers))
    assert len(w.transfers) == 1


def test_timeout_after_commit_without_key_duplicates() -> None:
    w = _world()
    w.fault_plan = build_fault_plan(
        seed=1,
        profile="clean",
        targeted=[
            FaultRule(
                fault_type=FaultType.TIMEOUT_AFTER_COMMIT,
                tool="create_transfer",
                nth_call=1,
            )
        ],
    )
    r1 = call_tool(w, "create_transfer", _transfer_args(None))
    assert not r1["ok"]
    assert len(w.transfers) == 1
    r2 = call_tool(w, "create_transfer", _transfer_args(None))
    assert r2["ok"]
    assert len(w.transfers) == 2


def test_timeout_before_commit_no_effect() -> None:
    w = _world()
    w.fault_plan = build_fault_plan(
        seed=1,
        profile="clean",
        targeted=[
            FaultRule(
                fault_type=FaultType.TIMEOUT_BEFORE_COMMIT,
                tool="create_transfer",
                nth_call=1,
            )
        ],
    )
    r1 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert not r1["ok"] and r1["error"]["code"] == "TIMEOUT"
    assert len(w.transfers) == 0
    r2 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert r2["ok"]
    assert len(w.transfers) == 1


def test_rate_limited_then_wait() -> None:
    w = _world()
    w.fault_plan = build_fault_plan(
        seed=1,
        profile="clean",
        targeted=[
            FaultRule(
                fault_type=FaultType.RATE_LIMITED,
                tool="create_transfer",
                nth_call=1,
                params={"retry_after_s": 10},
            )
        ],
    )
    r1 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert r1["error"]["code"] == "RATE_LIMITED"
    r2 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert r2["error"]["code"] == "RATE_LIMITED"
    call_tool(w, "wait", {"seconds": 10})
    r3 = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert r3["ok"]


def test_stale_read() -> None:
    w = _world()
    # create a transfer first with no faults
    call_tool(w, "create_transfer", _transfer_args("k0"))
    w.fault_plan = build_fault_plan(
        seed=1,
        profile="clean",
        targeted=[
            FaultRule(
                fault_type=FaultType.STALE_READ,
                tool="list_transfers",
                nth_call=1,
                params={"lag_s": 30},
            )
        ],
    )
    # advance a little so transfer is "newer" than cutoff relative to lag
    stale = call_tool(w, "list_transfers", {"account_id": "acc_000001"})
    assert stale["ok"]
    # with lag 30s and transfer just created (~2s ago after tool latency), may be filtered
    call_tool(w, "wait", {"seconds": 60})
    fresh = call_tool(w, "list_transfers", {"account_id": "acc_000001"})
    assert fresh["ok"]
    assert len(fresh["data"]["transfers"]) >= 1


def test_partial_failure_wait_resolves() -> None:
    w = _world()
    w.fault_plan = build_fault_plan(
        seed=1,
        profile="clean",
        targeted=[
            FaultRule(
                fault_type=FaultType.PARTIAL_FAILURE,
                tool="create_transfer",
                nth_call=1,
                params={"resolve_after_s": 20},
            )
        ],
    )
    r = call_tool(w, "create_transfer", _transfer_args("k1"))
    assert r["ok"]
    assert r["data"]["status"] == "pending"
    call_tool(w, "wait", {"seconds": 25})
    listed = call_tool(w, "list_transfers", {"account_id": "acc_000001"})
    assert listed["data"]["transfers"][0]["status"] == "completed"


def test_fault_plan_reproducible() -> None:
    a = build_fault_plan(7, "hostile")
    b = build_fault_plan(7, "hostile")
    assert [r.fault_type for r in a.rules] == [r.fault_type for r in b.rules]
