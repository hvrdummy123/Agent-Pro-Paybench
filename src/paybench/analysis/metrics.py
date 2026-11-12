"""Aggregate metrics and bootstrap confidence intervals."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from paybench.analysis.taxonomy import classify

BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 7


def _critical_violation(episode: dict[str, Any]) -> bool:
    for v in episode.get("violations") or []:
        if v.get("severity") == "critical":
            return True
    return "critical_violation" in (episode.get("failure_modes") or [])


def bootstrap_ci(
    values: list[float],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """95% bootstrap CI for the mean (percentile method)."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(samples):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(draw) / n)
    means.sort()
    lo_idx = max(0, int(0.025 * samples))
    hi_idx = min(samples - 1, int(0.975 * samples))
    return (means[lo_idx], means[hi_idx])


def pass_at_k(episodes: list[dict[str, Any]], k: int) -> float:
    """Fraction of (agent, task) groups with success on all of k trials."""
    groups: dict[tuple[str, str], list[tuple[int, bool]]] = defaultdict(list)
    for ep in episodes:
        key = (str(ep.get("agent", "unknown")), str(ep.get("task_id", "")))
        groups[key].append((int(ep.get("trial", 0)), bool(ep.get("success"))))
    hits = 0
    total = 0
    for outcomes in groups.values():
        if len(outcomes) < k:
            continue
        ordered = [ok for _, ok in sorted(outcomes, key=lambda x: x[0])]
        total += 1
        if all(ordered[:k]):
            hits += 1
    return hits / total if total else 0.0


def summarize(episodes: list[dict[str, Any]], k: int = 3) -> dict[str, Any]:
    """Summarize benchmark episodes keyed by agent."""
    if not episodes:
        return {"n_episodes": 0, "agents": {}, "taxonomy_counts": {}}

    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    taxonomy_counts: dict[str, int] = defaultdict(int)
    for ep in episodes:
        agent = str(ep.get("agent", "unknown"))
        by_agent[agent].append(ep)
        for code in classify(ep):
            taxonomy_counts[code] += 1

    agents: dict[str, Any] = {}
    for agent, eps in sorted(by_agent.items()):
        successes = [1.0 if ep.get("success") else 0.0 for ep in eps]
        partials = [float(ep.get("partial") or 0.0) for ep in eps]
        pass1 = sum(successes) / len(successes) if successes else 0.0
        ci = bootstrap_ci(successes)
        crit = sum(1 for ep in eps if _critical_violation(ep))
        n = len(eps)
        safety_violation_rate = crit / n if n else 0.0
        costs = [float(ep.get("cost_usd") or 0.0) for ep in eps]
        steps = [float(ep.get("steps") or 0.0) for ep in eps]
        succ_eps = [ep for ep in eps if ep.get("success")]
        cost_per_success = (
            sum(float(ep.get("cost_usd") or 0.0) for ep in succ_eps) / len(succ_eps)
            if succ_eps
            else None
        )
        agents[agent] = {
            "n_episodes": n,
            "pass_at_1": pass1,
            "pass_at_1_ci_low": ci[0],
            "pass_at_1_ci_high": ci[1],
            f"pass_pow_{k}": pass_at_k(eps, k),
            "safety_violation_rate": safety_violation_rate,
            "safety_rate": 1.0 - safety_violation_rate,
            "mean_partial": sum(partials) / len(partials) if partials else 0.0,
            "mean_cost_usd": sum(costs) / len(costs) if costs else 0.0,
            "cost_per_success_usd": cost_per_success,
            "mean_steps": sum(steps) / len(steps) if steps else 0.0,
        }

    return {
        "n_episodes": len(episodes),
        "k": k,
        "agents": agents,
        "taxonomy_counts": dict(sorted(taxonomy_counts.items())),
    }
