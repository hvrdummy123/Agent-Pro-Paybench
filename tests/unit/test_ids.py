"""Unit tests for IdFactory."""

from __future__ import annotations

from paybench.sim.ids import IdFactory


def test_deterministic_and_unique() -> None:
    a = IdFactory()
    b = IdFactory()
    ids_a = [a.customer() for _ in range(5)]
    ids_b = [b.customer() for _ in range(5)]
    assert ids_a == ids_b
    assert len(set(ids_a)) == 5
    assert ids_a[0] == "cus_000001"
    assert ids_a[1] == "cus_000002"


def test_prefixes() -> None:
    f = IdFactory()
    assert f.account().startswith("acc_")
    assert f.payment().startswith("txn_")
    assert f.transfer().startswith("trf_")
    assert f.refund().startswith("rfd_")
    assert f.dispute().startswith("dsp_")
    assert f.card().startswith("crd_")
    assert f.merchant().startswith("mch_")
    assert f.beneficiary().startswith("ben_")
    assert f.approval().startswith("apr_")


def test_snapshot_restore() -> None:
    f = IdFactory()
    _ = f.customer()
    snap = f.snapshot()
    _ = f.customer()
    f.restore(snap)
    assert f.customer() == "cus_000002"
