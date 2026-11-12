"""Google GenAI provider adapter (optional extra)."""

from __future__ import annotations

import os
from typing import Any


class GoogleProvider:
    name: str

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.name = f"google:{model_id}"
        try:
            from google import genai  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Install paybench[google] to use Google models") from exc
        key = os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        self._client = genai.Client(api_key=key)

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        # Minimal adapter: send last user text + declare function declarations.
        user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                user_text = str(m["content"])
                break
        decls = [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in tools
        ]
        resp = self._client.models.generate_content(
            model=self.model_id,
            contents=user_text or "Continue with tools.",
            config={"tools": [{"function_declarations": decls}]},
        )
        tool_calls: list[dict[str, Any]] = []
        for cand in getattr(resp, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc is not None:
                    tool_calls.append(
                        {
                            "name": fc.name,
                            "arguments": dict(getattr(fc, "args", {}) or {}),
                        }
                    )
        return {
            "tool_calls": tool_calls,
            "tokens_in": 0,
            "tokens_out": 0,
            "stop": not tool_calls,
        }

