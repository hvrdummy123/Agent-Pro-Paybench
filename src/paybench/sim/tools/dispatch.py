"""Tool dispatch with idempotency and fault injection."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from paybench.sim.faults import (
    FaultEvent,
    FaultType,
    before_error,
    choose_fault,
    timeout_after_mask,
)
from paybench.sim.models import CaseLogEntry, IdempotencyRecord, TransferStatus
from paybench.sim.tools.base import args_hash, err
from paybench.sim.tools.registry import REGISTRY
from paybench.sim.world import World


def _resolve_partials(world: World) -> None:
    plan = world.fault_plan
    if plan is None:
        return
    done: list[str] = []
    for tid, resolve_at in list(plan.pending_partials.items()):
        if world.clock.isoformat() >= resolve_at and tid in world.transfers:
            tr = world.transfers[tid]
            if tr.status == TransferStatus.PENDING:
                tr.status = TransferStatus.COMPLETED
                tr.completed_at = world.clock.isoformat()
            done.append(tid)
    for tid in done:
        plan.pending_partials.pop(tid, None)


def _apply_stale_filter(world: World, name: str, result: dict[str, Any]) -> dict[str, Any]:
    plan = world.fault_plan
    if plan is None or plan.stale_lag_s <= 0 or not result.get("ok"):
        return result
    cutoff = (world.clock.now - timedelta(seconds=plan.stale_lag_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = result.get("data")
    if not isinstance(data, dict):
        return result
    if name == "list_transfers" and "transfers" in data:
        filtered = [t for t in data["transfers"] if t.get("created_at", "") <= cutoff]
        return {**result, "data": {**data, "transfers": filtered}}
    if name == "list_payments" and "payments" in data:
        filtered = [p for p in data["payments"] if p.get("created_at", "") <= cutoff]
        return {**result, "data": {**data, "payments": filtered}}
    if (
        name == "get_payment"
        and isinstance(data.get("created_at"), str)
        and data["created_at"] > cutoff
    ):
        return err("NOT_FOUND", "payment not found")
    return result


def _log(
    world: World,
    name: str,
    args: dict[str, Any],
    result: dict[str, Any],
    fault: str | None,
    side_effects: list[str] | None = None,
) -> None:
    world.step += 1
    world.case_log.append(
        CaseLogEntry(
            step=world.step,
            tool=name,
            args=args,
            result=result,
            virtual_time=world.clock.isoformat(),
            side_effects=list(side_effects or []),
            fault=fault,
        )
    )


def call_tool(world: World, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a tool against the world with idempotency, faults, and logging."""
    args = dict(args or {})
    spec = REGISTRY.get(name)
    if spec is None:
        result = err("NOT_FOUND", f"unknown tool {name}")
        _log(world, name, args, result, None)
        return result

    _resolve_partials(world)

    key = args.get("idempotency_key")
    if spec.supports_idempotency and isinstance(key, str) and key:
        existing = world.idempotency.get(key)
        ah = args_hash({"tool": name, **{k: v for k, v in args.items() if k != "idempotency_key"}})
        if existing is not None:
            if existing.tool != name or existing.args_hash != ah:
                result = err("CONFLICT", "idempotency key reused with different arguments")
                if spec.latency_s:
                    world.clock.advance(spec.latency_s)
                _log(world, name, args, result, None)
                return result
            if spec.latency_s:
                world.clock.advance(spec.latency_s)
            result = existing.result
            _log(world, name, args, result, "idempotent_replay")
            return result

    plan = world.fault_plan
    fault_name: str | None = None
    decision = None
    if plan is not None:
        until = plan.rate_limited_until.get(name)
        if until and world.clock.isoformat() < until:
            if name != "wait" and spec.latency_s:
                world.clock.advance(spec.latency_s)
            until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
            retry_after = max(0, int((until_dt - world.clock.now).total_seconds()))
            result = err(
                "RATE_LIMITED",
                "rate limited",
                retryable=True,
                retry_after_s=retry_after,
            )
            _log(world, name, args, result, FaultType.RATE_LIMITED.value)
            return result
        decision = choose_fault(plan, name, world.rng)
        if decision.slow_extra_s:
            world.clock.advance(decision.slow_extra_s)
        pre = before_error(decision)
        if pre is not None:
            if name != "wait" and spec.latency_s:
                world.clock.advance(spec.latency_s)
            if decision.fault_type == FaultType.RATE_LIMITED:
                retry = int(decision.params.get("retry_after_s", 5))
                plan.rate_limited_until[name] = (
                    world.clock.now + timedelta(seconds=retry)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            assert decision.fault_type is not None
            plan.events.append(
                FaultEvent(
                    tool=name,
                    call_index=plan.call_counts.get(name, 0),
                    fault_type=decision.fault_type,
                    params=dict(decision.params),
                    virtual_time=world.clock.isoformat(),
                )
            )
            _log(world, name, args, pre, decision.fault_type.value)
            return pre
        if decision.fault_type == FaultType.STALE_READ:
            plan.stale_lag_s = int(decision.params.get("lag_s", 10))
            fault_name = decision.fault_type.value

    if name != "wait" and spec.latency_s:
        world.clock.advance(spec.latency_s)

    side_effects: list[str] = []
    result = spec.handler(world, args)

    if (
        plan is not None
        and decision is not None
        and decision.fault_type == FaultType.PARTIAL_FAILURE
        and name == "create_transfer"
        and result.get("ok")
    ):
        data = result.get("data")
        if isinstance(data, dict) and "id" in data:
            tid = str(data["id"])
            tr = world.transfers[tid]
            tr.status = TransferStatus.PENDING
            tr.completed_at = None
            resolve_s = int(decision.params.get("resolve_after_s", 15))
            resolve_at = (world.clock.now + timedelta(seconds=resolve_s)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            plan.pending_partials[tid] = resolve_at
            result = {**result, "data": tr.model_dump(mode="json")}
            fault_name = FaultType.PARTIAL_FAILURE.value

    if (
        plan is not None
        and decision is not None
        and decision.duplicate
        and result.get("ok")
        and not (isinstance(key, str) and key)
    ):
        _ = spec.handler(world, args)
        fault_name = FaultType.DUPLICATE_DELIVERY.value

    if spec.supports_idempotency and isinstance(key, str) and key and result.get("ok"):
        stored = result
        ah = args_hash({"tool": name, **{k: v for k, v in args.items() if k != "idempotency_key"}})
        effect_id = ""
        data = stored.get("data")
        if isinstance(data, dict) and "id" in data:
            effect_id = str(data["id"])
            side_effects.append(effect_id)
        world.idempotency[key] = IdempotencyRecord(
            key=key,
            tool=name,
            args_hash=ah,
            result=stored,
            effect_ids=[effect_id] if effect_id else [],
        )

    if plan is not None and decision is not None and decision.apply_after_mask and result.get("ok"):
        result = timeout_after_mask()
        fault_name = FaultType.TIMEOUT_AFTER_COMMIT.value
        plan.events.append(
            FaultEvent(
                tool=name,
                call_index=plan.call_counts.get(name, 0),
                fault_type=FaultType.TIMEOUT_AFTER_COMMIT,
                params=dict(decision.params),
                virtual_time=world.clock.isoformat(),
            )
        )

    if (
        plan is not None
        and (fault_name == FaultType.STALE_READ.value or plan.stale_lag_s > 0)
        and name in ("list_transfers", "list_payments", "get_payment")
    ):
        result = _apply_stale_filter(world, name, result)
        if decision is not None and decision.fault_type == FaultType.STALE_READ:
            plan.events.append(
                FaultEvent(
                    tool=name,
                    call_index=plan.call_counts.get(name, 0),
                    fault_type=FaultType.STALE_READ,
                    params=dict(decision.params),
                    virtual_time=world.clock.isoformat(),
                )
            )

    if world.debug_invariants:
        world.record_invariant_violations()

    _log(world, name, args, result, fault_name, side_effects)
    return result
