"""Mock LLM loop smoke test."""

from __future__ import annotations

from paybench.agents.llm_loop import LLMAgent
from paybench.agents.providers.mock import MockLLMProvider, ProviderTurn, ToolCall
from paybench.runner.episode import run_episode
from paybench.tasks.registry import get_task


def test_mock_llm_finishes() -> None:
    task = get_task("transfer_timeout_after_commit")
    provider = MockLLMProvider(
        script=[
            ProviderTurn(
                tool_calls=[
                    ToolCall(
                        "finish",
                        {"outcome": "cannot_complete", "summary": "mock stop"},
                    )
                ],
                stop=True,
            )
        ]
    )
    agent = LLMAgent(provider=provider, model_key="mock:mock")
    ep = run_episode(task, agent)
    assert ep["finished"]
    assert ep["tokens_in"] > 0
