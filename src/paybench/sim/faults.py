"""Deterministic fault injection for payment API messiness."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from paybench.sim.rng import Rng


class FaultType(StrEnum):
    UNAVAILABLE_BEFORE = "UNAVAILABLE_BEFORE"
    TIMEOUT_BEFORE_COMMIT = "TIMEOUT_BEFORE_COMMIT"
    TIMEOUT_AFTER_COMMIT = "TIMEOUT_AFTER_COMMIT"
    RATE_LIMITED = "RATE_LIMITED"
    STALE_READ = "STALE_READ"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    DUPLICATE_DELIVERY = "DUPLICATE_DELIVERY"
    SLOW = "SLOW"


@dataclass
class FaultRule:
    """A deterministic fault rule."""

    fault_type: FaultType
    tool: str | None = None  # None = any tool (usually filtered by profile)
    nth_call: int | None = None  # 1-based call count for matching tool
    probability: float | None = None  # used with rng for background flakiness
    params: dict[str, Any] = field(default_factory=dict)
    tools: frozenset[str] | None = None  # alternate multi-tool matcher


@dataclass
class FaultEvent:
    tool: str
    call_index: int
    fault_type: FaultType
    params: dict[str, Any]
    virtual_time: str


@dataclass
class FaultPlan:
    """Executable fault plan derived from profile + seed + targeted rules."""

    rules: list[FaultRule] = field(default_factory=list)
    call_counts: dict[str, int] = field(default_factory=dict)
    events: list[FaultEvent] = field(default_factory=list)
    rate_limited_until: dict[str, str] = field(default_factory=dict)
    stale_lag_s: int = 0
    pending_partials: dict[str, str] = field(default_factory=dict)  # transfer_id -> resolve_at

    def snapshot(self) -> FaultPlan:
        return deepcopy(self)

    def restore(self, other: FaultPlan) -> None:
        snap = deepcopy(other)
        self.rules = snap.rules
        self.call_counts = snap.call_counts
        self.events = snap.events
        self.rate_limited_until = snap.rate_limited_until
        self.stale_lag_s = snap.stale_lag_s
        self.pending_partials = snap.pending_partials


def profile_rules(profile: str, rng: Rng) -> list[FaultRule]:
    """Background rules for clean/flaky/hostile profiles."""
    _ = rng  # reserved for future seeded rule generation
    if profile == "clean":
        return []
    rules: list[FaultRule] = []
    if profile in ("flaky", "hostile"):
        rules.append(
            FaultRule(
                fault_type=FaultType.UNAVAILABLE_BEFORE,
                probability=0.05,
                tools=frozenset(
                    {
                        "create_transfer",
                        "issue_refund",
                        "open_dispute",
                        "list_payments",
                        "get_payment",
                    }
                ),
            )
        )
        rules.append(
            FaultRule(
                fault_type=FaultType.RATE_LIMITED,
                probability=0.03,
                params={"retry_after_s": 5},
                tools=frozenset({"create_transfer", "issue_refund", "list_payments"}),
            )
        )
    if profile == "hostile":
        rules.append(
            FaultRule(
                fault_type=FaultType.TIMEOUT_AFTER_COMMIT,
                probability=0.08,
                tools=frozenset({"create_transfer", "issue_refund"}),
            )
        )
        rules.append(
            FaultRule(
                fault_type=FaultType.STALE_READ,
                probability=0.1,
                params={"lag_s": 10},
                tools=frozenset({"list_transfers", "list_payments", "get_payment"}),
            )
        )
        rules.append(
            FaultRule(
                fault_type=FaultType.PARTIAL_FAILURE,
                probability=0.05,
                params={"resolve_after_s": 15},
                tools=frozenset({"create_transfer"}),
            )
        )
    return rules


def build_fault_plan(
    seed: int,
    profile: str = "clean",
    targeted: list[FaultRule] | None = None,
) -> FaultPlan:
    rng = Rng(seed).child("faults")
    rules = list(targeted or []) + profile_rules(profile, rng)
    return FaultPlan(rules=rules)


@dataclass
class FaultDecision:
    fault_type: FaultType | None = None
    params: dict[str, Any] = field(default_factory=dict)
    apply_before: bool = False
    apply_after_mask: bool = False  # TIMEOUT_AFTER_COMMIT: run then mask as timeout
    duplicate: bool = False
    slow_extra_s: int = 0


def _matches(rule: FaultRule, tool: str) -> bool:
    if rule.tool is not None and rule.tool != tool:
        return False
    return not (rule.tools is not None and tool not in rule.tools)


def choose_fault(
    plan: FaultPlan,
    tool: str,
    rng: Rng,
) -> FaultDecision:
    """Pick at most one fault for this call (targeted nth_call wins over probability)."""
    plan.call_counts[tool] = plan.call_counts.get(tool, 0) + 1
    n = plan.call_counts[tool]
    frng = rng.child("faults")

    targeted: FaultRule | None = None
    background: FaultRule | None = None
    for rule in plan.rules:
        if not _matches(rule, tool):
            continue
        if rule.nth_call is not None:
            if rule.nth_call == n:
                targeted = rule
                break
            continue
        if (
            rule.probability is not None
            and background is None
            and frng.child(f"{tool}:{n}:{rule.fault_type}").random() < rule.probability
        ):
            background = rule

    chosen = targeted or background
    if chosen is None:
        return FaultDecision()

    ft = chosen.fault_type
    params = dict(chosen.params)
    if ft == FaultType.UNAVAILABLE_BEFORE:
        return FaultDecision(fault_type=ft, params=params, apply_before=True)
    if ft == FaultType.TIMEOUT_BEFORE_COMMIT:
        return FaultDecision(fault_type=ft, params=params, apply_before=True)
    if ft == FaultType.TIMEOUT_AFTER_COMMIT:
        return FaultDecision(fault_type=ft, params=params, apply_after_mask=True)
    if ft == FaultType.RATE_LIMITED:
        return FaultDecision(fault_type=ft, params=params, apply_before=True)
    if ft == FaultType.STALE_READ:
        return FaultDecision(fault_type=ft, params=params)
    if ft == FaultType.PARTIAL_FAILURE:
        return FaultDecision(fault_type=ft, params=params)
    if ft == FaultType.DUPLICATE_DELIVERY:
        return FaultDecision(fault_type=ft, params=params, duplicate=True)
    if ft == FaultType.SLOW:
        return FaultDecision(
            fault_type=ft,
            params=params,
            slow_extra_s=int(params.get("extra_s", 5)),
        )
    return FaultDecision()


def before_error(decision: FaultDecision) -> dict[str, Any] | None:
    """Return an error response if the fault fires before commit."""
    if decision.fault_type is None or not decision.apply_before:
        return None
    ft = decision.fault_type
    if ft == FaultType.UNAVAILABLE_BEFORE:
        return {
            "ok": False,
            "error": {
                "code": "UNAVAILABLE",
                "message": "service unavailable",
                "retryable": True,
                "retry_after_s": decision.params.get("retry_after_s"),
            },
        }
    if ft == FaultType.TIMEOUT_BEFORE_COMMIT:
        return {
            "ok": False,
            "error": {
                "code": "TIMEOUT",
                "message": "timeout before commit",
                "retryable": True,
                "retry_after_s": None,
            },
        }
    if ft == FaultType.RATE_LIMITED:
        retry = int(decision.params.get("retry_after_s", 5))
        return {
            "ok": False,
            "error": {
                "code": "RATE_LIMITED",
                "message": "rate limited",
                "retryable": True,
                "retry_after_s": retry,
            },
        }
    return None


def timeout_after_mask() -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "TIMEOUT",
            "message": "timeout after commit (outcome uncertain)",
            "retryable": True,
            "retry_after_s": None,
        },
    }
