"""Unit tests for World hash and snapshot."""

from __future__ import annotations

from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account
from paybench.sim.models import Account, AccountStatus, Customer, KycStatus, RiskTier
from paybench.sim.world import World


def _seed_minimal(world: World) -> None:
    cus = Customer(
        id="cus_000001",
        name="Ada Lovelace",
        email="ada@example.com",
        phone="+910000000001",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
        verification_factors={"dob": "1815-12-10"},
    )
    world.customers[cus.id] = cus
    acc = Account(
        id="acc_000001",
        customer_id=cus.id,
        currency="INR",
        status=AccountStatus.ACTIVE,
    )
    world.accounts[acc.id] = acc
    world.ledger.post(
        [
            Entry(BANK_FLOAT, -10_000, "INR", "seed"),
            Entry(customer_account(cus.id), 10_000, "INR", "seed"),
        ]
    )


def test_state_hash_deterministic() -> None:
    w1 = World(seed=1)
    w2 = World(seed=1)
    _seed_minimal(w1)
    _seed_minimal(w2)
    assert w1.state_hash() == w2.state_hash()


def test_state_hash_changes_on_mutation() -> None:
    w = World(seed=1)
    _seed_minimal(w)
    h0 = w.state_hash()
    w.clock.advance(2)
    assert w.state_hash() != h0


def test_snapshot_restore_preserves_future() -> None:
    w = World(seed=42)
    _seed_minimal(w)
    snap = w.snapshot()
    w.clock.advance(10)
    w.step = 5
    h_after = w.state_hash()
    w.restore(snap)
    assert w.step == 0
    w.clock.advance(10)
    w.step = 5
    assert w.state_hash() == h_after


def test_invariants_i1_clean() -> None:
    w = World(seed=1)
    _seed_minimal(w)
    assert w.check_invariants() == []
