"""Task registry and world instantiation."""

from __future__ import annotations

from typing import Any

from paybench.sim.world import World
from paybench.tasks.builders import build_world
from paybench.tasks.core_tasks import HEADLINE_TASKS
from paybench.tasks.schema import GoldCall, TaskSpec


def _load_catalog() -> list[TaskSpec]:
    try:
        from paybench.tasks.catalog import CATALOG_TASKS

        return list(CATALOG_TASKS)
    except ImportError:
        return []


def all_tasks() -> list[TaskSpec]:
    tasks = list(HEADLINE_TASKS) + _load_catalog()
    seen: set[str] = set()
    out: list[TaskSpec] = []
    for t in tasks:
        if t.id in seen:
            continue
        seen.add(t.id)
        out.append(t)
    return out


def get_task(task_id: str) -> TaskSpec:
    for t in all_tasks():
        if t.id == task_id:
            return t
    raise KeyError(f"unknown task {task_id}")


def core_tasks() -> list[TaskSpec]:
    return [t for t in all_tasks() if t.core]


def tasks_by_category(category: str) -> list[TaskSpec]:
    return [t for t in all_tasks() if t.category.value == category]


def instantiate_world(task: TaskSpec, variant: int = 0) -> World:
    world_cfg = dict(task.world)
    seed_offset = int(world_cfg.get("seed_offset", 0))
    template = str(world_cfg.get("template", "standard_small"))
    planted = dict(world_cfg.get("planted") or {})
    return build_world(
        seed=seed_offset,
        template=template,
        planted=planted,
        customer_facts=dict(task.customer_facts),
        fault_profile=task.fault_profile,
        scripted_faults=list(task.scripted_faults),
        variant=variant,
    )


def resolve_args(args: dict[str, Any], world: World) -> dict[str, Any]:
    """Replace $planted_key placeholders in gold/tool args."""
    out: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str) and v.startswith("$"):
            key = v[1:]
            if key not in world.planted:
                raise KeyError(f"placeholder {v} not in planted world")
            out[k] = world.planted[key]
        else:
            out[k] = v
    return out


def resolve_gold(task: TaskSpec, world: World) -> list[GoldCall]:
    return [GoldCall(tool=g.tool, args=resolve_args(g.args, world)) for g in task.gold]
