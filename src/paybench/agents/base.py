"""Agent protocol and episode context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from paybench.sim.tools.base import ToolSpec
from paybench.tasks.schema import TaskSpec


@dataclass
class AgentResult:
    finished: bool
    steps: int
    notes: str = ""
    error: str | None = None


@dataclass
class EpisodeContext:
    task: TaskSpec
    system_prompt: str
    user_message: str
    tool_specs: list[ToolSpec]
    call_tool: Callable[[str, dict[str, Any]], dict[str, Any]]
    max_steps: int
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent(Protocol):
    name: str

    def run(self, episode: EpisodeContext) -> AgentResult: ...
