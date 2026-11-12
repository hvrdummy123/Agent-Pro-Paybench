"""Payment action tools: verify, refund, transfer, reverse, approval."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from paybench.config import (
    DAILY_OUTBOUND_LIMIT_INR_PAISE,
    DAILY_OUTBOUND_LIMIT_USD_CENTS,
    MAX_FAILED_VERIFICATIONS,
    VERIFY_LOCK_SECONDS,
)
from paybench.sim.ledger import BANK_FLOAT, Entry, customer_account, merchant_settlement
from paybench.sim.models import (
    Approval,
    ApprovalStatus,
    PaymentStatus,
    Refund,
    RefundStatus,
    Transfer,
    TransferStatus,
)
from paybench.sim.tools.base import err, ok
from paybench.sim.world import World


def verify_customer(world: World, args: dict[str, Any]) -> dict[str, Any]:
    cid = args.get("customer_id")
    factor = args.get("factor")
    value = args.get("value")
    if not isinstance(cid, str) or cid not in world.customers:
        return err("NOT_FOUND", f"customer {cid} not found")
    if not isinstance(factor, str) or not isinstance(value, str):
        return err("INVALID_ARGUMENT", "factor and value required")
    cust = world.customers[cid]
    if cust.locked:
        if cust.locked_until and cust.locked_until > world.clock.isoformat():
            return err("POLICY_VIOLATION", "customer locked after failed verifications")
        cust.locked = False
        cust.locked_until = None
        cust.failed_verifications = 0
    expected = cust.verification_factors.get(factor)
    if expected is None or expected != value:
        cust.failed_verifications += 1
        if cust.failed_verifications >= MAX_FAILED_VERIFICATIONS:
            cust.locked = True
            unlock = world.clock.now + timedelta(seconds=VERIFY_LOCK_SECONDS)
            cust.locked_until = unlock.strftime("%Y-%m-%dT%H:%M:%SZ")
        return err("NOT_VERIFIED", "verification failed")
    world.verified_customers.add(cid)
    cust.failed_verifications = 0
    return ok({"customer_id": cid, "verified": True, "factor": factor})


def issue_refund(world: World, args: dict[str, Any]) -> dict[str, Any]:
    pid = args.get("payment_id")
    amount = args.get("amount")
    reason = args.get("reason", "")
    if not isinstance(pid, str) or pid not in world.payments:
        return err("NOT_FOUND", f"payment {pid} not found")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        return err("INVALID_ARGUMENT", "amount must be positive int")
    pay = world.payments[pid]
    remaining = pay.amount - pay.refunded_amount
    if amount > remaining:
        return err("LIMIT_EXCEEDED", f"refund exceeds remaining {remaining}")
    if pay.status in (PaymentStatus.FAILED, PaymentStatus.REVERSED):
        return err("INVALID_ARGUMENT", f"cannot refund payment in status {pay.status}")
    rid = world.ids.refund()
    refund = Refund(
        id=rid,
        payment_id=pid,
        amount=amount,
        currency=pay.currency,
        status=RefundStatus.COMPLETED,
        created_at=world.clock.isoformat(),
        reason=str(reason),
        idempotency_key=args.get("idempotency_key")
        if isinstance(args.get("idempotency_key"), str)
        else None,
    )
    world.refunds[rid] = refund
    pay.refunded_amount += amount
    if pay.refunded_amount >= pay.amount:
        pay.status = PaymentStatus.REFUNDED
    else:
        pay.status = PaymentStatus.PARTIALLY_REFUNDED
    # ledger: merchant settlement -> customer
    world.ledger.post(
        [
            Entry(merchant_settlement(pay.merchant_id), -amount, pay.currency, rid, "refund"),
            Entry(customer_account(pay.customer_id), amount, pay.currency, rid, "refund"),
        ]
    )
    return ok(refund.model_dump(mode="json"))


def create_transfer(world: World, args: dict[str, Any]) -> dict[str, Any]:
    from_acc = args.get("from_account_id")
    bid = args.get("beneficiary_id")
    amount = args.get("amount")
    memo = str(args.get("memo") or "")
    if not isinstance(from_acc, str) or from_acc not in world.accounts:
        return err("NOT_FOUND", f"account {from_acc} not found")
    if not isinstance(bid, str) or bid not in world.beneficiaries:
        return err("NOT_FOUND", f"beneficiary {bid} not found")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        return err("INVALID_ARGUMENT", "amount must be positive int")
    acc = world.accounts[from_acc]
    ben = world.beneficiaries[bid]
    if ben.customer_id != acc.customer_id:
        return err("INVALID_ARGUMENT", "beneficiary does not belong to account owner")
    day = world.clock.day_start().strftime("%Y-%m-%d")
    if acc.daily_outbound_day != day:
        acc.daily_outbound_used = 0
        acc.daily_outbound_day = day
    bal = world.account_balance(from_acc)
    if amount > bal:
        return err("LIMIT_EXCEEDED", "insufficient balance")
    tid = world.ids.transfer()
    key = args.get("idempotency_key") if isinstance(args.get("idempotency_key"), str) else None
    transfer = Transfer(
        id=tid,
        from_account=from_acc,
        beneficiary_id=bid,
        amount=amount,
        currency=acc.currency,
        status=TransferStatus.COMPLETED,
        idempotency_key=key,
        created_at=world.clock.isoformat(),
        completed_at=world.clock.isoformat(),
        memo=memo,
    )
    world.transfers[tid] = transfer
    world.ledger.post(
        [
            Entry(customer_account(acc.customer_id), -amount, acc.currency, tid, "transfer"),
            Entry(BANK_FLOAT, amount, acc.currency, tid, "transfer"),
        ]
    )
    acc.daily_outbound_used += amount
    # Soft limit: policy grades over-limit; tool does not hard-block.
    _ = DAILY_OUTBOUND_LIMIT_INR_PAISE if acc.currency == "INR" else DAILY_OUTBOUND_LIMIT_USD_CENTS
    return ok(transfer.model_dump(mode="json"))


def reverse_transfer(world: World, args: dict[str, Any]) -> dict[str, Any]:
    tid = args.get("transfer_id")
    reason = str(args.get("reason") or "")
    if not isinstance(tid, str) or tid not in world.transfers:
        return err("NOT_FOUND", f"transfer {tid} not found")
    tr = world.transfers[tid]
    if tr.status == TransferStatus.REVERSED:
        return err("CONFLICT", "transfer already reversed")
    if tr.status == TransferStatus.FAILED:
        return err("INVALID_ARGUMENT", "cannot reverse failed transfer")
    if tr.status == TransferStatus.COMPLETED:
        acc = world.accounts[tr.from_account]
        world.ledger.post(
            [
                Entry(BANK_FLOAT, -tr.amount, tr.currency, f"{tid}:rev", reason),
                Entry(
                    customer_account(acc.customer_id),
                    tr.amount,
                    tr.currency,
                    f"{tid}:rev",
                    reason,
                ),
            ]
        )
        day = world.clock.day_start().strftime("%Y-%m-%d")
        if acc.daily_outbound_day == day:
            acc.daily_outbound_used = max(0, acc.daily_outbound_used - tr.amount)
    tr.status = TransferStatus.REVERSED
    return ok(tr.model_dump(mode="json"))


def request_approval(world: World, args: dict[str, Any]) -> dict[str, Any]:
    kind = args.get("kind")
    subject_id = args.get("subject_id")
    if not isinstance(kind, str) or not isinstance(subject_id, str):
        return err("INVALID_ARGUMENT", "kind and subject_id required")
    amount = args.get("amount")
    if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool)):
        return err("INVALID_ARGUMENT", "amount must be int")
    justification = str(args.get("justification") or "")
    aid = world.ids.approval()
    # Resolve after deterministic delay from seed (default 30s); some denials via planted
    delay = 30
    will_deny = False
    planted = world.planted.get("approvals") or {}
    if isinstance(planted, dict) and subject_id in planted:
        cfg = planted[subject_id]
        if isinstance(cfg, dict):
            delay = int(cfg.get("delay_s", delay))
            will_deny = bool(cfg.get("deny", False))
    resolve_at = (world.clock.now + timedelta(seconds=delay)).strftime("%Y-%m-%dT%H:%M:%SZ")
    appr = Approval(
        id=aid,
        kind=kind,
        subject_id=subject_id,
        amount=amount if isinstance(amount, int) else None,
        justification=justification,
        status=ApprovalStatus.PENDING,
        created_at=world.clock.isoformat(),
        resolve_at=resolve_at,
    )
    # stash decision intent
    world.session_flags[f"approval_deny:{aid}"] = will_deny
    world.approvals[aid] = appr
    return ok(appr.model_dump(mode="json"))


def get_approval(world: World, args: dict[str, Any]) -> dict[str, Any]:
    aid = args.get("approval_id")
    if not isinstance(aid, str) or aid not in world.approvals:
        return err("NOT_FOUND", f"approval {aid} not found")
    appr = world.approvals[aid]
    if (
        appr.status == ApprovalStatus.PENDING
        and appr.resolve_at
        and world.clock.isoformat() >= appr.resolve_at
    ):
        deny = bool(world.session_flags.get(f"approval_deny:{aid}", False))
        appr.status = ApprovalStatus.DENIED if deny else ApprovalStatus.APPROVED
        appr.decided_at = world.clock.isoformat()
    return ok(appr.model_dump(mode="json"))


def flag_payment(world: World, args: dict[str, Any]) -> dict[str, Any]:
    pid = args.get("payment_id")
    flag = args.get("flag")
    note = str(args.get("note") or "")
    if not isinstance(pid, str) or pid not in world.payments:
        return err("NOT_FOUND", f"payment {pid} not found")
    if flag not in ("suspected_fraud", "needs_review"):
        return err("INVALID_ARGUMENT", "invalid flag")
    pay = world.payments[pid]
    if flag not in pay.flags:
        pay.flags.append(str(flag))
    _ = note
    return ok({"payment_id": pid, "flags": list(pay.flags)})
