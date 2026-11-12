"""Generic tool-calling loop for LLM agents."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from paybench.agents.base import AgentResult, EpisodeContext
from paybench.agents.providers.mock import MockLLMProvider

__all__ = ["LLMAgent", "LLMProvider", "MockLLMProvider", "run_llm_loop"]


class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


@dataclass
class LLMAgent:
    """Agent that drives the simulator via an LLM provider."""

    provider: LLMProvider
    model_key: str = "mock:mock"
    max_tokens: int = 32_000
    name: str = "llm"

    def run(self, ctx: EpisodeContext) -> AgentResult:
        return run_llm_loop(
            ctx,
            self.provider,
            max_tokens=self.max_tokens,
            model_key=self.model_key,
        )


def run_llm_loop(
    ctx: EpisodeContext,
    provider: LLMProvider,
    *,
    max_tokens: int = 32_000,
    model_key: str = "mock:mock",
) -> AgentResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": ctx.system_prompt},
        {"role": "user", "content": ctx.user_message},
    ]
    tools_json = [
        {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        for t in ctx.tool_specs
    ]
    steps = 0
    tokens_in = 0
    tokens_out = 0
    finished = False
    error: str | None = None
    for _ in range(ctx.max_steps):
        steps += 1
        if tokens_in + tokens_out >= max_tokens:
            error = "token budget exceeded"
            break
        turn = provider.complete(messages, tools_json)
        tokens_in += int(turn.get("tokens_in") or 0)
        tokens_out += int(turn.get("tokens_out") or 0)
        tool_calls = turn.get("tool_calls") or []
        if not tool_calls:
            if turn.get("stop"):
                error = error or "provider stopped without tool calls"
            break
        for tc in tool_calls:
            name = str(tc.get("name", ""))
            args = tc.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            result = ctx.call_tool(name, dict(args))
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_call": {"name": name, "arguments": args},
                }
            )
            messages.append({"role": "tool", "name": name, "content": json.dumps(result)})
            if name == "finish" and result.get("ok"):
                finished = True
                break
        if finished:
            break
        if turn.get("stop"):
            break
    if steps >= ctx.max_steps and not finished:
        error = error or "max_steps reached"
    meta = ctx.metadata
    meta["tokens_in"] = tokens_in
    meta["tokens_out"] = tokens_out
    meta["model_key"] = model_key
    return AgentResult(finished=finished, steps=steps, error=error)
