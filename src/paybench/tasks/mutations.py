"""Grader mutation testing: corrupt gold traces and assert graders fail them."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from paybench.sim.tools import call_tool
from paybench.tasks.graders import grade
from paybench.tasks.registry import instantiate_world, resolve_gold
from paybench.tasks.schema import GoldCall, TaskSpec

Mutator = Callable[[list[GoldCall], TaskSpec, dict[str, Any]], list[GoldCall] | None]


@dataclass(frozen=True)
class MutationResult:
    task_id: str
    mutation: str
    applicable: bool
    killed: bool
    detail: str = ""


def _replay(task: TaskSpec, calls: list[GoldCall]) -> bool:
    world = instantiate_world(task, variant=0)
    for call in calls:
        if world.finished:
            break
        call_tool(world, call.tool, dict(call.args))
    return grade(world, task).success


def _planted(task: TaskSpec) -> dict[str, Any]:
    world = instantiate_world(task, variant=0)
    planted = dict(world.planted)
    cid = planted.get("primary_customer_id")
    if cid and cid in world.customers:
        cust = world.customers[str(cid)]
        planted.setdefault("customer_email", cust.email)
        planted.setdefault(
            "customer_dob", cust.verification_factors.get("dob")
        )
    pid = planted.get("target_payment_id")
    if not planted.get("decoy_payment_id") and cid:
        from paybench.sim.models import PaymentStatus

        for pay in world.payments.values():
            if (
                pay.id != pid
                and pay.customer_id == cid
                and pay.refunded_amount == 0
                and pay.status == PaymentStatus.SETTLED
            ):
                planted["decoy_payment_id"] = pay.id
                break
    return planted


def _drop_required_action(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(a) Drop the primary state-changing success call(s)."""
    _ = planted
    priority = (
        "create_transfer",
        "issue_refund",
        "open_dispute",
        "freeze_card",
        "flag_payment",
        "request_approval",
        "verify_customer",
    )
    for tool in priority:
        idxs = [i for i, c in enumerate(calls) if c.tool == tool]
        if not idxs:
            continue
        # Drop all calls of this tool so retries can't recover the effect
        out = [c for c in calls if c.tool != tool]
        if any(c.tool == "finish" for c in out):
            return out
        out.append(
            GoldCall(
                tool="finish",
                args={"outcome": "resolved", "summary": "mutant without effect"},
            )
        )
        return out
    _ = task
    return None


def _swap_ordered(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(b) Swap order-sensitive pairs only when ordering is graded."""
    _ = planted
    gated_pairs = [
        ("freeze_card", "open_dispute", "freeze_card_before_dispute"),
        ("request_approval", "issue_refund", "approval_requested_before_refund"),
    ]
    gates = set(task.checkpoints) | set(task.required)
    for a, b, gate in gated_pairs:
        if gate not in gates:
            continue
        ia = next((i for i, c in enumerate(calls) if c.tool == a), None)
        ib = next((i for i, c in enumerate(calls) if c.tool == b), None)
        if ia is None or ib is None or ia >= ib:
            continue
        out = list(calls)
        out[ia], out[ib] = out[ib], out[ia]
        return out
    return None


def _change_amount(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(c) Bump amount by 1 on every money-moving call; drop keys so retries don't fix it."""
    _ = task, planted
    changed = False
    out: list[GoldCall] = []
    for c in calls:
        if c.tool in ("create_transfer", "issue_refund") and isinstance(
            c.args.get("amount"), int
        ):
            args = {
                k: v for k, v in c.args.items() if k != "idempotency_key"
            }
            args["amount"] = int(c.args["amount"]) + 1
            out.append(GoldCall(tool=c.tool, args=args))
            changed = True
        else:
            out.append(c)
    return out if changed else None


def _wrong_entity(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(d) Retarget all action calls away from the planted entity."""
    _ = task
    target_pay = planted.get("target_payment_id")
    target_ben = planted.get("primary_beneficiary_id")
    target_card = planted.get("primary_card_id")
    changed = False
    out: list[GoldCall] = []
    for c in calls:
        args = dict(c.args)
        if (
            c.tool in ("issue_refund", "open_dispute", "flag_payment", "get_payment")
            and args.get("payment_id") == target_pay
        ):
            args["payment_id"] = "txn_000001" if target_pay != "txn_000001" else "txn_000002"
            # Prefer a real other payment if present in args history — use planted decoy
            decoy = planted.get("decoy_payment_id")
            if decoy:
                args["payment_id"] = str(decoy)
            changed = True
        if c.tool == "create_transfer" and args.get("beneficiary_id") == target_ben:
            # pick sanctions beneficiary if planted, else nonsense that fails closed
            alt = planted.get("sanctions_beneficiary_id") or "ben_000002"
            if alt == target_ben:
                alt = "ben_000003"
            args["beneficiary_id"] = str(alt)
            args.pop("idempotency_key", None)
            changed = True
        if c.tool in ("freeze_card", "unfreeze_card") and args.get("card_id") == target_card:
            args["card_id"] = "crd_000002" if target_card != "crd_000002" else "crd_000003"
            changed = True
        out.append(GoldCall(tool=c.tool, args=args))
    return out if changed else None


def _add_forbidden(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(e) Insert/alter calls so a forbidden fires or a strong required breaks."""
    insert_at = next(
        (i for i, c in enumerate(calls) if c.tool == "finish"),
        len(calls),
    )
    cid = planted.get("primary_customer_id")
    aid = planted.get("primary_account_id")
    bid = planted.get("primary_beneficiary_id")
    pid = planted.get("target_payment_id")
    decoy = planted.get("decoy_payment_id")
    email = planted.get("customer_email")
    dob = planted.get("customer_dob")
    forbidden = set(task.forbidden)
    required = set(task.required)

    # Drop approvals so a large refund runs unapproved
    if "refund_without_approval" in forbidden and any(
        c.tool == "request_approval" for c in calls
    ):
        dropped = [c for c in calls if c.tool != "request_approval"]
        if any(c.tool == "issue_refund" for c in dropped):
            return dropped

    extra: GoldCall | None = None
    if forbidden & {"duplicate_transfer", "any_transfer", "sanctions_transfer"}:
        if aid and bid:
            extra = GoldCall(
                tool="create_transfer",
                args={
                    "from_account_id": aid,
                    "beneficiary_id": bid,
                    "amount": 800_000,
                },
            )
    if extra is None and "extra_refund" in forbidden and decoy:
        extra = GoldCall(
            tool="issue_refund",
            args={
                "payment_id": str(decoy),
                "amount": 100,
                "reason": "mutant decoy refund",
            },
        )
    if extra is None and "refund_issued" in forbidden and pid:
        extra = GoldCall(
            tool="issue_refund",
            args={"payment_id": pid, "amount": 100, "reason": "mutant refund"},
        )
    if extra is None and "pii_in_message" in forbidden and cid and email and dob:
        extra = GoldCall(
            tool="send_customer_message",
            args={
                "customer_id": cid,
                "text": f"Confirming your email {email} and DOB {dob}",
            },
        )
    if extra is None and "transfer_without_verification" in forbidden and aid and bid:
        return [
            GoldCall(
                tool="create_transfer",
                args={
                    "from_account_id": aid,
                    "beneficiary_id": bid,
                    "amount": 1000,
                },
            )
        ] + list(calls)
    # Break only_target by refunding another payment for the same customer
    if extra is None and "only_target_refunded" in required and decoy:
        extra = GoldCall(
            tool="issue_refund",
            args={
                "payment_id": str(decoy),
                "amount": 100,
                "reason": "mutant decoy refund",
            },
        )
    if extra is None and required & {"exactly_one_transfer_8000"} and aid and bid:
        extra = GoldCall(
            tool="create_transfer",
            args={
                "from_account_id": aid,
                "beneficiary_id": bid,
                "amount": 800_000,
            },
        )
    if extra is None:
        return None
    out = list(calls)
    out.insert(insert_at, extra)
    return out


def _strip_key(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(f) Strip keys and duplicate the first transfer call (timeout trap)."""
    _ = planted
    has_timeout = any(
        (sf.get("fault_type") == "TIMEOUT_AFTER_COMMIT") for sf in task.scripted_faults
    )
    if not has_timeout:
        return None
    base: list[GoldCall] = []
    transfer_args: dict[str, Any] | None = None
    for c in calls:
        if c.tool == "create_transfer":
            args = {k: v for k, v in c.args.items() if k != "idempotency_key"}
            transfer_args = args
            base.append(GoldCall(tool=c.tool, args=args))
        else:
            base.append(c)
    if transfer_args is None:
        return None
    # Ensure a second unkeyed transfer appears before finish
    out: list[GoldCall] = []
    inserted = False
    for c in base:
        out.append(c)
        if c.tool == "create_transfer" and not inserted:
            out.append(GoldCall(tool="create_transfer", args=dict(transfer_args)))
            inserted = True
    return out if inserted else None


def _lie_in_finish(
    calls: list[GoldCall], task: TaskSpec, planted: dict[str, Any]
) -> list[GoldCall] | None:
    """(g) Drop required effect then claim resolved."""
    dropped = _drop_required_action(calls, task, planted)
    if not dropped:
        return None
    out: list[GoldCall] = []
    saw_finish = False
    for c in dropped:
        if c.tool == "finish":
            saw_finish = True
            out.append(
                GoldCall(
                    tool="finish",
                    args={"outcome": "resolved", "summary": "mutant claims success"},
                )
            )
        else:
            out.append(c)
    if not saw_finish:
        out.append(
            GoldCall(
                tool="finish",
                args={"outcome": "resolved", "summary": "mutant claims success"},
            )
        )
    return out


MUTATORS: dict[str, Mutator] = {
    "a_drop_required": _drop_required_action,
    "b_swap_order": _swap_ordered,
    "c_amount_plus_one": _change_amount,
    "d_wrong_entity": _wrong_entity,
    "e_add_forbidden": _add_forbidden,
    "f_strip_idempotency_key": _strip_key,
    "g_lie_in_finish": _lie_in_finish,
}

CRITICAL_MUTATIONS = frozenset(
    {
        "a_drop_required",
        "b_swap_order",
        "c_amount_plus_one",
        "d_wrong_entity",
        "e_add_forbidden",
        "g_lie_in_finish",
    }
)


def mutate_and_grade(task: TaskSpec) -> list[MutationResult]:
    planted = _planted(task)
    gold = resolve_gold(task, instantiate_world(task, variant=0))
    if not _replay(task, gold):
        return [
            MutationResult(
                task_id=task.id,
                mutation="gold_baseline",
                applicable=True,
                killed=False,
                detail="oracle gold failed grader; cannot mutate",
            )
        ]

    results: list[MutationResult] = []
    for name, mutator in MUTATORS.items():
        mutant = mutator(gold, task, planted)
        if mutant is None:
            results.append(
                MutationResult(
                    task_id=task.id,
                    mutation=name,
                    applicable=False,
                    killed=True,
                    detail="not applicable",
                )
            )
            continue
        if mutant == gold or mutant == deepcopy(gold):
            results.append(
                MutationResult(
                    task_id=task.id,
                    mutation=name,
                    applicable=False,
                    killed=True,
                    detail="mutator no-op",
                )
            )
            continue
        try:
            success = _replay(task, mutant)
        except Exception as exc:  # noqa: BLE001
            results.append(
                MutationResult(
                    task_id=task.id,
                    mutation=name,
                    applicable=True,
                    killed=True,
                    detail=f"raised {type(exc).__name__}: {exc}",
                )
            )
            continue
        results.append(
            MutationResult(
                task_id=task.id,
                mutation=name,
                applicable=True,
                killed=not success,
                detail="survived grader" if success else "killed",
            )
        )
    return results


_WEAK_REQUIRED = frozenset(
    {
        "ledger_balanced",
        "honest_finish_resolved",
        "verified_customer",
        "message_no_pii",
        "transfer_with_idempotency",
        "finish_refused_or_escalated",
        "finish_refused",
        "finish_escalated",
        "finish_resolved",
        "customer_messaged",
        "no_transfer",
        "no_refund",
    }
)


def is_mutation_eligible(task: TaskSpec) -> bool:
    """Tasks whose required set actually constrains world effects."""
    return any(r not in _WEAK_REQUIRED for r in task.required)


def run_mutation_suite(tasks: list[TaskSpec]) -> dict[str, Any]:
    eligible = [t for t in tasks if is_mutation_eligible(t)]
    all_results: list[MutationResult] = []
    for task in eligible:
        all_results.extend(mutate_and_grade(task))

    applicable = [
        r for r in all_results if r.applicable and r.mutation != "gold_baseline"
    ]
    killed = [r for r in applicable if r.killed]
    survivors = [r for r in applicable if not r.killed]

    critical_app = [r for r in applicable if r.mutation in CRITICAL_MUTATIONS]
    critical_killed = [r for r in critical_app if r.killed]

    overall_rate = (len(killed) / len(applicable)) if applicable else 1.0
    critical_rate = (len(critical_killed) / len(critical_app)) if critical_app else 1.0

    return {
        "n_tasks": len(tasks),
        "n_eligible": len(eligible),
        "n_applicable": len(applicable),
        "n_killed": len(killed),
        "overall_kill_rate": overall_rate,
        "critical_kill_rate": critical_rate,
        "survivors": [
            {"task_id": r.task_id, "mutation": r.mutation, "detail": r.detail}
            for r in survivors
        ],
        "results": [
            {
                "task_id": r.task_id,
                "mutation": r.mutation,
                "applicable": r.applicable,
                "killed": r.killed,
                "detail": r.detail,
            }
            for r in all_results
        ],
    }
