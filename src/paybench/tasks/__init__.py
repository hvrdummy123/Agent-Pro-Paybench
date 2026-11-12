"""Benchmark tasks, builders, and graders."""

from __future__ import annotations

from paybench.tasks.graders import GradeResult, grade
from paybench.tasks.registry import all_tasks, get_task, instantiate_world
from paybench.tasks.schema import TaskSpec

__all__ = [
    "GradeResult",
    "TaskSpec",
    "all_tasks",
    "get_task",
    "grade",
    "instantiate_world",
]
