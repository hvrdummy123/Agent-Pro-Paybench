"""Oracle agent: replays gold tool calls."""

from __future__ import annotations

from paybench.agents.base import AgentResult, EpisodeContext
from paybench.tasks.registry import resolve_gold


class OracleAgent:
    name = "oracle"

    def run(self, episode: EpisodeContext) -> AgentResult:
        world = episode.metadata["world"]
        gold = resolve_gold(episode.task, world)
        steps = 0
        for call in gold:
            if steps >= episode.max_steps:
                return AgentResult(finished=world.finished, steps=steps, error="max_steps")
            episode.call_tool(call.tool, call.args)
            steps += 1
            if world.finished:
                break
        return AgentResult(finished=world.finished, steps=steps)
