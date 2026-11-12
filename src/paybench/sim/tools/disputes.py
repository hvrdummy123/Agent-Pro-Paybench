"""Dispute tools."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from paybench.sim.models import (
    Dispute,
    DisputeEvidence,
    DisputeReason,
    DisputeStatus,
    PaymentStatus,
)
from paybench.sim.tools.base import err, ok
from paybench.sim.world import World


def open_dispute(world: World, args: dict[str, Any]) -> dict[str, Any]:
    pid = args.get("payment_id")
    reason = args.get("reason_code")
    if not isinstance(pid, str) or pid not in world.payments:
        return err("NOT_FOUND", f"payment {pid} not found")
    try:
        reason_code = DisputeReason(str(reason))
    except ValueError:
        return err("INVALID_ARGUMENT", f"invalid reason_code {reason}")
    pay = world.payments[pid]
    if pay.dispute_id:
        return err("CONFLICT", "payment already has a dispute")
    did = world.ids.dispute()
    deadline = (world.clock.now + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dsp = Dispute(
        id=did,
        payment_id=pid,
        reason_code=reason_code,
        status=DisputeStatus.OPENED,
        opened_at=world.clock.isoformat(),
        evidence_deadline=deadline,
    )
    world.disputes[did] = dsp
    pay.dispute_id = did
    pay.status = PaymentStatus.DISPUTED
    return ok(dsp.model_dump(mode="json"))


def submit_dispute_evidence(world: World, args: dict[str, Any]) -> dict[str, Any]:
    did = args.get("dispute_id")
    etype = args.get("evidence_type")
    content = args.get("content")
    if not isinstance(did, str) or did not in world.disputes:
        return err("NOT_FOUND", f"dispute {did} not found")
    if not isinstance(etype, str) or not isinstance(content, str):
        return err("INVALID_ARGUMENT", "evidence_type and content required")
    dsp = world.disputes[did]
    if world.clock.isoformat() > dsp.evidence_deadline:
        return err("POLICY_VIOLATION", "evidence deadline passed")
    ev = DisputeEvidence(
        evidence_type=etype,
        content=content,
        submitted_at=world.clock.isoformat(),
    )
    dsp.evidence.append(ev)
    if dsp.status == DisputeStatus.OPENED:
        dsp.status = DisputeStatus.EVIDENCE_REQUESTED
    return ok(dsp.model_dump(mode="json"))
