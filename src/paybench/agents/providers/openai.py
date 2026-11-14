"""OpenAI provider adapter (optional extra)."""

from __future__ import annotations

import json
import os
from typing import Any


class OpenAIProvider:
    name: str

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.name = f"openai:{model_id}"
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Install paybench[openai] to use OpenAI models") from exc
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self._client = OpenAI(api_key=key)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]
        converted: list[dict[str, Any]] = []
        for m in messages:
            role = m.get("role")
            if role == "tool":
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(m.get("name")),
                        "content": str(m.get("content") or ""),
                    }
                )
            elif role == "assistant" and (m.get("tool_calls") or m.get("tool_call")):
                tcs = list(m.get("tool_calls") or [m["tool_call"]])
                converted.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.get("id") or tc["name"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc.get("arguments") or {}),
                                },
                            }
                            for tc in tcs
                        ],
                    }
                )
            else:
                converted.append({"role": role, "content": m.get("content") or ""})
        resp = self._client.chat.completions.create(
            model=self.model_id,
            messages=converted,
            tools=oai_tools,
        )
        msg = resp.choices[0].message
        tool_calls: list[dict[str, Any]] = []
        for tc in msg.tool_calls or []:
            args: dict[str, Any]
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                {"name": tc.function.name, "arguments": args, "id": tc.id}
            )
        usage = resp.usage
        return {
            "tool_calls": tool_calls,
            "tokens_in": int(getattr(usage, "prompt_tokens", 0) or 0),
            "tokens_out": int(getattr(usage, "completion_tokens", 0) or 0),
            "stop": not tool_calls,
        }
