"""Null agent: immediately finishes cannot_complete."""

from __future__ import annotations

from paybench.agents.base import AgentResult, EpisodeContext


class NullAgent:
    name = "null"

    def run(self, episode: EpisodeContext) -> AgentResult:
        episode.call_tool(
            "finish",
            {"outcome": "cannot_complete", "summary": "null agent"},
        )
        return AgentResult(finished=True, steps=1)
