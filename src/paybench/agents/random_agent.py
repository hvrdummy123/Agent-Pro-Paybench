"""Seeded random agent — mostly fails."""

from __future__ import annotations

from paybench.agents.base import AgentResult, EpisodeContext
from paybench.sim.tools import REGISTRY


class RandomAgent:
    name = "random"

    def run(self, episode: EpisodeContext) -> AgentResult:
        world = episode.metadata["world"]
        rng = world.rng.child("random_agent")
        tools = [n for n in sorted(REGISTRY.tools) if n != "finish"]
        steps = 0
        for _ in range(min(episode.max_steps - 1, 15)):
            name = rng.choice(tools)
            spec = REGISTRY.tools[name]
            args: dict[str, object] = {}
            # fill required with planted ids when possible
            props = spec.parameters.get("properties", {})
            required = spec.parameters.get("required", [])
            for key in required:
                if key.endswith("_id") and f"primary_{key}" in world.planted:
                    args[key] = world.planted[f"primary_{key}"]
                elif key == "customer_id":
                    args[key] = world.planted.get(
                        "primary_customer_id", next(iter(world.customers))
                    )
                elif key == "payment_id":
                    args[key] = world.planted.get("target_payment_id", next(iter(world.payments)))
                elif key == "query":
                    args[key] = "a"
                elif key == "question":
                    args[key] = "dob?"
                elif key == "text":
                    args[key] = "hello"
                elif key == "reason":
                    args[key] = "random"
                elif key == "reason_code":
                    args[key] = "duplicate"
                elif key == "factor":
                    args[key] = "dob"
                elif key == "value":
                    args[key] = "wrong"
                elif key == "amount":
                    args[key] = 100
                elif key == "seconds":
                    args[key] = 1
                elif key == "flag":
                    args[key] = "needs_review"
                elif key == "kind":
                    args[key] = "refund"
                elif key == "subject_id":
                    args[key] = world.planted.get("target_payment_id", next(iter(world.payments)))
                elif key == "summary":
                    args[key] = "random"
                elif key in props and props[key].get("type") == "integer":
                    args[key] = 1
                else:
                    args[key] = "x"
            episode.call_tool(name, args)
            steps += 1
            if world.finished:
                return AgentResult(finished=True, steps=steps)
        episode.call_tool(
            "finish",
            {"outcome": "cannot_complete", "summary": "random stop"},
        )
        return AgentResult(finished=True, steps=steps + 1)
