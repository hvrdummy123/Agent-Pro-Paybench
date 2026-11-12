"""Control tools: wait and finish."""

from __future__ import annotations

from typing import Any

from paybench.config import MAX_WAIT_S
from paybench.sim.tools.base import err, ok
from paybench.sim.world import World

_OUTCOMES = frozenset({"resolved", "escalated", "refused", "cannot_complete"})


def wait(world: World, args: dict[str, Any]) -> dict[str, Any]:
    seconds = args.get("seconds")
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        return err("INVALID_ARGUMENT", "seconds must be int")
    if seconds < 0 or seconds > MAX_WAIT_S:
        return err("INVALID_ARGUMENT", f"seconds must be 0..{MAX_WAIT_S}")
    # wait itself advances clock; dispatcher also applies tool latency — skip double for wait
    world.clock.wait(seconds)
    return ok({"now": world.clock.isoformat(), "advanced_s": seconds})


def finish(world: World, args: dict[str, Any]) -> dict[str, Any]:
    outcome = args.get("outcome")
    summary = args.get("summary")
    if outcome not in _OUTCOMES:
        return err("INVALID_ARGUMENT", f"outcome must be one of {sorted(_OUTCOMES)}")
    if not isinstance(summary, str):
        return err("INVALID_ARGUMENT", "summary must be string")
    if world.finished:
        return err("CONFLICT", "already finished")
    world.finished = True
    world.finish_outcome = str(outcome)
    world.finish_summary = summary
    if outcome == "escalated":
        world.escalated = True
    return ok({"outcome": outcome, "summary": summary, "finished": True})
