"""Benchmark self-validation: Oracle/Null/Naive gates."""

from __future__ import annotations

from paybench.agents import NaiveAgent, NullAgent, OracleAgent, RandomAgent
from paybench.runner.episode import run_episode
from paybench.tasks.registry import all_tasks, core_tasks, get_task


def test_task_counts() -> None:
    tasks = all_tasks()
    assert len(tasks) == 50
    assert len(core_tasks()) == 25
    cats = {t.category.value for t in tasks}
    assert cats == {
        "lookup",
        "ops",
        "disputes",
        "policy",
        "faults",
        "adversarial",
        "longhorizon",
    }


def test_oracle_100_percent() -> None:
    agent = OracleAgent()
    for task in all_tasks():
        ep = run_episode(task, agent)
        assert ep["success"], f"Oracle failed {task.id}: {ep['failure_modes']} {ep['violations']}"


def test_oracle_variants_differ_but_pass() -> None:
    task = get_task("transfer_timeout_after_commit")
    hashes = []
    for v in range(3):
        ep = run_episode(task, OracleAgent(), variant=v)
        assert ep["success"]
        hashes.append(ep["state_hash"])
    assert len(set(hashes)) == 3


def test_null_fails_action_tasks() -> None:
    agent = NullAgent()
    for task in all_tasks():
        if task.expected_outcome in ("refused", "escalated") and not task.required:
            continue
        # refusal tasks that only need finish_refused may pass null — skip those
        if task.expected_outcome in ("refused", "escalated") and set(task.required) <= {
            "finish_refused_or_escalated",
            "finish_refused",
            "finish_escalated",
        }:
            continue
        ep = run_episode(task, agent)
        if any(
            r
            not in (
                "finish_refused_or_escalated",
                "finish_refused",
                "finish_escalated",
                "honest_finish_resolved",
            )
            for r in task.required
        ):
            assert not ep["success"], f"Null unexpectedly passed {task.id}"


def test_naive_fails_adversarial_and_faults() -> None:
    agent = NaiveAgent()
    for task in all_tasks():
        if task.category.value not in ("adversarial", "faults"):
            continue
        ep = run_episode(task, agent)
        assert not ep["success"], f"Naive passed trap task {task.id}"


def test_random_low_success() -> None:
    agent = RandomAgent()
    successes = sum(1 for t in all_tasks() if run_episode(t, agent)["success"])
    rate = successes / len(all_tasks())
    assert rate <= 0.05, f"Random success rate {rate}"


def test_headline_naive_labels() -> None:
    ep = run_episode(get_task("transfer_timeout_after_commit"), NaiveAgent())
    assert "duplicate_transfer" in ep["forbidden_hit"]
    ep2 = run_episode(get_task("memo_injection_refund_all"), NaiveAgent())
    assert not ep2["success"]
