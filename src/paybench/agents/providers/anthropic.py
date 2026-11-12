"""Anthropic provider adapter (optional extra)."""

from __future__ import annotations

import os
from typing import Any


class AnthropicProvider:
    name: str

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.name = f"anthropic:{model_id}"
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "Install paybench[anthropic] to use Anthropic models"
            ) from exc
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=key)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        anth_tools = [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]
        system = ""
        converted: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system = str(m.get("content") or "")
                continue
            if role == "tool":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.get("tool_use_id") or m.get("name"),
                                "content": str(m.get("content") or ""),
                            }
                        ],
                    }
                )
                continue
            if role == "assistant" and m.get("tool_call"):
                tc = m["tool_call"]
                converted.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tc.get("id") or tc["name"],
                                "name": tc["name"],
                                "input": tc.get("arguments") or {},
                            }
                        ],
                    }
                )
                continue
            converted.append({"role": role, "content": m.get("content") or ""})
        resp = self._client.messages.create(
            model=self.model_id,
            max_tokens=2048,
            system=system,
            messages=converted,
            tools=anth_tools,
        )
        tool_calls: list[dict[str, Any]] = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append(
                    {
                        "name": block.name,
                        "arguments": dict(block.input),
                        "id": block.id,
                    }
                )
        usage = getattr(resp, "usage", None)
        return {
            "tool_calls": tool_calls,
            "tokens_in": int(getattr(usage, "input_tokens", 0) or 0),
            "tokens_out": int(getattr(usage, "output_tokens", 0) or 0),
            "stop": not tool_calls,
        }
