"""Google GenAI provider adapter (optional extra)."""

from __future__ import annotations

import os
from typing import Any


def _part_thought_signature(part: Any) -> Any:
    sig = getattr(part, "thought_signature", None)
    if sig is not None:
        return sig
    # Some SDK builds nest it; tolerate dict dumps.
    dumped = part.model_dump(exclude_none=True) if hasattr(part, "model_dump") else {}
    return dumped.get("thought_signature")


_GEMINI_SCHEMA_DROP = frozenset(
    {
        "additionalProperties",
        "additional_properties",
        "$schema",
        "$id",
        "$defs",
        "definitions",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
)


def _gemini_schema(node: Any) -> Any:
    """Strip JSON-Schema fields Gemini's function-calling API rejects."""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for k, v in node.items():
            if k in _GEMINI_SCHEMA_DROP:
                continue
            out[k] = _gemini_schema(v)
        return out
    if isinstance(node, list):
        return [_gemini_schema(x) for x in node]
    return node


class GoogleProvider:
    name: str

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.name = f"google:{model_id}"
        try:
            from google import genai  # type: ignore[import-not-found]
            from google.genai import types  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not importable in this Python. "
                "In your active venv run: python -m pip install -e '.[google]' "
                f"(original error: {exc})"
            ) from exc
        key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY (or GEMINI_API_KEY) not set")
        # Gemini 3.x + large tool schemas often need >60s on free tier.
        # Override with GOOGLE_HTTP_TIMEOUT_MS (milliseconds).
        try:
            timeout_ms = int(os.environ.get("GOOGLE_HTTP_TIMEOUT_MS", "180000"))
        except ValueError:
            timeout_ms = 180_000
        timeout_ms = max(30_000, timeout_ms)
        self._client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=2),
            ),
        )
        self._types = types

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        types = self._types
        decls = [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": _gemini_schema(t["parameters"]),
            }
            for t in tools
        ]
        system = ""
        contents: list[Any] = []
        i = 0
        while i < len(messages):
            m = messages[i]
            role = m.get("role")
            if role == "system":
                system = str(m.get("content") or "")
                i += 1
                continue
            if role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=str(m.get("content") or ""))],
                    )
                )
                i += 1
                continue
            # Coalesce consecutive assistant tool_call + tool pairs into
            # [model: all functionCall parts] then [user: all functionResponse parts]
            # so Gemini 3 parallel calls keep a single thought_signature on FC1.
            if role == "assistant" and (m.get("tool_call") or m.get("tool_calls")):
                fc_parts: list[Any] = []
                fr_parts: list[Any] = []
                while i < len(messages):
                    am = messages[i]
                    if am.get("role") != "assistant":
                        break
                    tcs: list[dict[str, Any]]
                    if am.get("tool_calls"):
                        tcs = list(am["tool_calls"])
                    elif am.get("tool_call"):
                        tcs = [dict(am["tool_call"])]
                    else:
                        break
                    i += 1
                    for tc in tcs:
                        part_kwargs: dict[str, Any] = {
                            "function_call": types.FunctionCall(
                                name=str(tc.get("name") or ""),
                                args=dict(tc.get("arguments") or {}),
                            )
                        }
                        sig = tc.get("thought_signature")
                        if sig is not None:
                            part_kwargs["thought_signature"] = sig
                        elif not fc_parts:
                            # Last-resort escape hatch if history was rebuilt without sigs.
                            part_kwargs["thought_signature"] = (
                                "skip_thought_signature_validator"
                            )
                        fc_parts.append(types.Part(**part_kwargs))
                        if i < len(messages) and messages[i].get("role") == "tool":
                            tm = messages[i]
                            i += 1
                            raw = tm.get("content")
                            if isinstance(raw, str):
                                try:
                                    import json

                                    response_obj: Any = json.loads(raw)
                                except Exception:  # noqa: BLE001
                                    response_obj = {"result": raw}
                            elif isinstance(raw, dict):
                                response_obj = raw
                            else:
                                response_obj = {"result": str(raw)}
                            fr_parts.append(
                                types.Part.from_function_response(
                                    name=str(tm.get("name") or tc.get("name") or ""),
                                    response=response_obj
                                    if isinstance(response_obj, dict)
                                    else {"result": response_obj},
                                )
                            )
                if fc_parts:
                    contents.append(types.Content(role="model", parts=fc_parts))
                if fr_parts:
                    contents.append(types.Content(role="user", parts=fr_parts))
                continue
            if role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part(text=str(m.get("content") or ""))],
                    )
                )
                i += 1
                continue
            if role == "tool":
                # Orphan tool result (should be rare after coalescing).
                raw = m.get("content")
                try:
                    import json

                    response_obj = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:  # noqa: BLE001
                    response_obj = {"result": str(raw)}
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=str(m.get("name") or "tool"),
                                response=response_obj
                                if isinstance(response_obj, dict)
                                else {"result": response_obj},
                            )
                        ],
                    )
                )
                i += 1
                continue
            i += 1

        if not contents:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part(text="Continue with tools.")],
                )
            ]

        config: dict[str, Any] = {
            "tools": [{"function_declarations": decls}],
            "automatic_function_calling": {"disable": True},
        }
        if system:
            config["system_instruction"] = system

        resp = self._client.models.generate_content(
            model=self.model_id,
            contents=contents,
            config=config,
        )

        tool_calls: list[dict[str, Any]] = []
        for cand in getattr(resp, "candidates", None) or []:
            content = getattr(cand, "content", None)
            for part in getattr(content, "parts", None) or []:
                fc = getattr(part, "function_call", None)
                if fc is None:
                    continue
                entry: dict[str, Any] = {
                    "name": fc.name,
                    "arguments": dict(getattr(fc, "args", {}) or {}),
                }
                sig = _part_thought_signature(part)
                if sig is not None:
                    entry["thought_signature"] = sig
                tool_calls.append(entry)

        usage = getattr(resp, "usage_metadata", None)
        tokens_in = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        tokens_out = (
            int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        )
        return {
            "tool_calls": tool_calls,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "stop": not tool_calls,
        }
