"""Grader mutation tests — corrupt gold must fail grading."""

from __future__ import annotations

from paybench.tasks.mutations import (
    CRITICAL_MUTATIONS,
    is_mutation_eligible,
    mutate_and_grade,
    run_mutation_suite,
)
from paybench.tasks.registry import core_tasks, get_task

HEADLINES = (
    "transfer_timeout_after_commit",
    "memo_injection_refund_all",
    "dispute_unauthorized_order_of_ops",
)


def test_headlines_are_mutation_eligible() -> None:
    for tid in HEADLINES:
        assert is_mutation_eligible(get_task(tid))


def test_headline_mutations_kill_critical() -> None:
    for tid in HEADLINES:
        results = mutate_and_grade(get_task(tid))
        for r in results:
            if not r.applicable or r.mutation == "gold_baseline":
                continue
            if r.mutation in CRITICAL_MUTATIONS:
                assert r.killed, f"{tid} {r.mutation} survived: {r.detail}"


def test_eligible_core_mutation_kill_rates() -> None:
    summary = run_mutation_suite(core_tasks())
    assert summary["n_eligible"] >= 3
    assert summary["critical_kill_rate"] == 1.0, summary["survivors"]
    assert summary["overall_kill_rate"] >= 0.95, summary["survivors"]
