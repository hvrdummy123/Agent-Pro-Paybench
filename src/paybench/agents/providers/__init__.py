"""LLM provider adapters."""

from __future__ import annotations

from typing import Any


def build_provider(model: str) -> Any:
    """Factory: provider:model_id → provider instance."""
    if ":" not in model:
        raise ValueError("model must be provider:model_id")
    provider, mid = model.split(":", 1)
    if provider == "anthropic":
        from paybench.agents.providers.anthropic import AnthropicProvider

        return AnthropicProvider(mid)
    if provider == "openai":
        from paybench.agents.providers.openai import OpenAIProvider

        return OpenAIProvider(mid)
    if provider == "google":
        from paybench.agents.providers.google import GoogleProvider

        return GoogleProvider(mid)
    if provider == "mock":
        from paybench.agents.providers.mock import MockLLMProvider, ProviderTurn, ToolCall

        return MockLLMProvider(
            script=[
                ProviderTurn(
                    tool_calls=[
                        ToolCall(
                            "finish",
                            {"outcome": "cannot_complete", "summary": "mock"},
                        )
                    ],
                    stop=True,
                )
            ]
        )
    raise ValueError(f"unknown provider {provider}")


__all__ = ["build_provider"]
