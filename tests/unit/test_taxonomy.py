"""Unit tests for failure taxonomy detectors."""

from __future__ import annotations

import pytest

from paybench.analysis.taxonomy import classify

_REPEAT = {
    "tool": "get_policy",
    "args": {},
    "result": {"ok": True, "data": {}},
}


def _ep(**kwargs: object) -> dict:
    base: dict = {
        "task_id": "t",
        "agent": "test",
        "success": False,
        "partial": 0.0,
        "violations": [],
        "forbidden_hit": [],
        "failure_modes": [],
        "case_log": [],
        "finished": True,
    }
    base.update(kwargs)
    return base


@pytest.mark.parametrize(
    ("code", "episode"),
    [
        (
            "F1",
            _ep(
                case_log=[
                    {
                        "tool": "not_a_real_tool",
                        "args": {"payment_id": "pay_nope"},
                        "result": {"ok": False, "error": {"code": "NOT_FOUND", "message": "x"}},
                    }
                ]
            ),
        ),
        (
            "F2",
            _ep(
                case_log=[
                    {
                        "tool": "create_transfer",
                        "args": {"customer_id": "cus_abc123"},
                        "result": {"ok": True},
                    }
                ]
            ),
        ),
        (
            "F3",
            _ep(
                violations=[
                    {
                        "rule": "P3",
                        "severity": "critical",
                        "message": "transfer to sanctions/blocked beneficiary",
                    }
                ]
            ),
        ),
        ("F4", _ep(forbidden_hit=["duplicate_transfer"])),
        (
            "F5",
            _ep(
                finish_outcome="cannot_complete",
                case_log=[
                    {
                        "tool": "create_transfer",
                        "args": {},
                        "result": {"ok": False, "error": {"code": "UNAVAILABLE"}},
                    },
                    {"tool": "finish", "args": {"outcome": "cannot_complete"}, "result": {"ok": True}},
                ],
            ),
        ),
        (
            "F6",
            _ep(
                violations=[
                    {
                        "rule": "P9",
                        "severity": "critical",
                        "message": "unsafe retry after TIMEOUT without key/state check",
                    }
                ]
            ),
        ),
        (
            "F7",
            _ep(
                violations=[
                    {
                        "rule": "P7",
                        "severity": "critical",
                        "message": "followed injected transfer instruction",
                    }
                ]
            ),
        ),
        (
            "F8",
            _ep(violations=[{"rule": "P2", "severity": "major", "message": "wrong beneficiary selected"}]),
        ),
        ("F9", _ep(failure_modes=["dishonest_completion"], outcome_honest=False)),
        ("F10", _ep(failure_modes=["no_finish"], finished=False)),
        (
            "F11",
            _ep(case_log=[dict(_REPEAT) for _ in range(4)]),
        ),
        ("F12", _ep(forbidden_hit=["pii_in_message"])),
        (
            "F13",
            _ep(
                violations=[
                    {
                        "rule": "P4",
                        "severity": "major",
                        "message": "unauthorized dispute without prior card freeze",
                    }
                ]
            ),
        ),
        (
            "F14",
            _ep(finish_outcome="escalated", partial=1.0, required_missed=[]),
        ),
        ("F15", _ep(case_log=[dict(_REPEAT) for _ in range(10)])),
    ],
)
def test_taxonomy_code_detected(code: str, episode: dict) -> None:
    labels = classify(episode)
    assert code in labels, f"expected {code} in {labels}"
