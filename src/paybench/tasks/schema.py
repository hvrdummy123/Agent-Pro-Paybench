"""Task specification schema."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskCategory(StrEnum):
    LOOKUP = "lookup"
    OPS = "ops"
    DISPUTES = "disputes"
    POLICY = "policy"
    FAULTS = "faults"
    ADVERSARIAL = "adversarial"
    LONGHORIZON = "longhorizon"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class GoldCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: TaskCategory
    difficulty: Difficulty
    core: bool = False
    title: str
    instruction: str
    world: dict[str, Any] = Field(default_factory=dict)
    customer_facts: dict[str, str] = Field(default_factory=dict)
    fault_profile: str = "clean"
    scripted_faults: list[dict[str, Any]] = Field(default_factory=list)
    max_steps: int = 25
    tools: str | list[str] = "all"
    checkpoints: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    expected_outcome: str = "resolved"
    traps: list[str] = Field(default_factory=list)
    gold: list[GoldCall] = Field(default_factory=list)
    policy_sections: list[str] = Field(default_factory=list)
