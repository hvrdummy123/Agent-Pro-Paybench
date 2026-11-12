"""Collect Oracle vs Naive traces for the compare page."""

from __future__ import annotations

from typing import Any

from paybench.agents.naive import NaiveAgent
from paybench.agents.oracle import OracleAgent
from paybench.runner.episode import run_episode
from paybench.tasks.registry import get_task

COMPARE_TASK_ID = "transfer_timeout_after_commit"


def _slim(ep: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": ep.get("task_id"),
        "agent": ep.get("agent"),
        "success": ep.get("success"),
        "partial": ep.get("partial"),
        "forbidden_hit": ep.get("forbidden_hit") or [],
        "failure_modes": ep.get("failure_modes") or [],
        "finish_outcome": ep.get("finish_outcome"),
        "case_log": [
            {
                "step": e.get("step"),
                "tool": e.get("tool"),
                "fault": e.get("fault"),
                "result": {
                    "ok": (e.get("result") or {}).get("ok"),
                    "error": (e.get("result") or {}).get("error"),
                },
            }
            for e in ep.get("case_log") or []
        ],
    }


def collect_compare_payload(task_id: str = COMPARE_TASK_ID) -> dict[str, Any]:
    task = get_task(task_id)
    naive = run_episode(task, NaiveAgent())
    oracle = run_episode(task, OracleAgent())
    return {
        "task_id": task.id,
        "title": task.title,
        "instruction": task.instruction,
        "traps": list(task.traps),
        "naive": _slim(naive),
        "oracle": _slim(oracle),
    }
