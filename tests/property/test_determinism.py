"""Property tests for determinism of World."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account
from paybench.sim.models import Account, AccountStatus, Customer, KycStatus, RiskTier
from paybench.sim.world import World


def _world(seed: int) -> World:
    w = World(seed=seed)
    cus = Customer(
        id="cus_000001",
        name="Test User",
        email="t@example.com",
        phone="+910000000000",
        kyc_status=KycStatus.VERIFIED,
        risk_tier=RiskTier.LOW,
    )
    w.customers[cus.id] = cus
    w.accounts["acc_000001"] = Account(
        id="acc_000001",
        customer_id=cus.id,
        currency="INR",
        status=AccountStatus.ACTIVE,
    )
    w.ledger.post(
        [
            Entry(BANK_FLOAT, -50_000, "INR", "seed"),
            Entry(customer_account(cus.id), 50_000, "INR", "seed"),
        ]
    )
    return w


@given(seed=st.integers(min_value=0, max_value=10_000), steps=st.integers(1, 20))
@settings(max_examples=50)
def test_same_seed_same_hash_after_advances(seed: int, steps: int) -> None:
    w1 = _world(seed)
    w2 = _world(seed)
    for _ in range(steps):
        w1.clock.advance(2)
        w2.clock.advance(2)
    assert w1.state_hash() == w2.state_hash()


@given(seed=st.integers(0, 1000))
@settings(max_examples=30)
def test_snapshot_restore_identical_future(seed: int) -> None:
    w = _world(seed)
    snap = w.snapshot()
    w.clock.advance(7)
    h = w.state_hash()
    w.restore(snap)
    w.clock.advance(7)
    assert w.state_hash() == h
