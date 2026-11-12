"""Mock LLM provider for deterministic harness tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ProviderTurn:
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: str | None = None
    stop: bool = False


@dataclass
class MockLLMProvider:
    """Returns a scripted sequence of tool calls (cycles when exhausted)."""

    script: list[ProviderTurn]
    name: str = "mock:mock"
    tokens_in: int = 100
    tokens_out: int = 50
    _index: int = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        _ = messages, tools
        if not self.script:
            return {
                "tool_calls": [],
                "message": "",
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "stop": True,
            }
        turn = self.script[min(self._index, len(self.script) - 1)]
        self._index += 1
        return {
            "tool_calls": [
                {"name": tc.name, "arguments": dict(tc.arguments)} for tc in turn.tool_calls
            ],
            "message": turn.message or "",
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "stop": turn.stop,
        }
