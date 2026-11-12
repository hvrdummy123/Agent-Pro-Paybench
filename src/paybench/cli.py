"""PayBench CLI."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from paybench import __version__

app = typer.Typer(
    name="paybench",
    help="PayBench: deterministic fintech agent benchmark.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        console.print(__version__)
        raise typer.Exit(0)


@app.command("list-tasks")
def list_tasks(
    category: str | None = typer.Option(None, "--category"),
    core: bool = typer.Option(False, "--core"),
) -> None:
    """List benchmark tasks."""
    from paybench.tasks.registry import all_tasks

    table = Table(title="PayBench tasks")
    table.add_column("id")
    table.add_column("category")
    table.add_column("diff")
    table.add_column("core")
    for t in all_tasks():
        if category and t.category.value != category:
            continue
        if core and not t.core:
            continue
        table.add_row(t.id, t.category.value, t.difficulty.value, "★" if t.core else "")
    console.print(table)


@app.command("show-task")
def show_task(task_id: str) -> None:
    """Show a task specification."""
    from paybench.tasks.registry import get_task

    t = get_task(task_id)
    console.print_json(t.model_dump_json(indent=2))


@app.command("run")
def run_cmd(
    agent: str = typer.Option("oracle", "--agent"),
    tasks: str = typer.Option("core", "--tasks", help="all|core|comma-ids"),
    trials: int = typer.Option(1, "--trials"),
    variants: int = typer.Option(1, "--variants"),
    out: Path | None = typer.Option(None, "--out"),
) -> None:
    """Run agents on tasks and write JSONL results."""
    from paybench.agents import NaiveAgent, NullAgent, OracleAgent, RandomAgent
    from paybench.agents.base import Agent
    from paybench.runner.episode import run_episode
    from paybench.tasks.registry import all_tasks, core_tasks, get_task

    agents: dict[str, Agent] = {
        "oracle": OracleAgent(),
        "null": NullAgent(),
        "naive": NaiveAgent(),
        "random": RandomAgent(),
    }
    if agent not in agents:
        console.print(f"[red]Unknown agent {agent}[/red]")
        raise typer.Exit(1)
    ag = agents[agent]
    if tasks == "all":
        task_list = all_tasks()
    elif tasks == "core":
        task_list = core_tasks()
    else:
        task_list = [get_task(x.strip()) for x in tasks.split(",")]

    out_dir = out or Path("results") / f"{agent}_{tasks}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "episodes.jsonl"
    n_ok = 0
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for t in task_list:
            for trial in range(trials):
                for variant in range(variants):
                    ep = run_episode(t, ag, variant=variant, trial=trial)
                    f.write(json.dumps(ep) + "\n")
                    n += 1
                    n_ok += int(ep["success"])
    console.print(f"Wrote {path}  pass={n_ok}/{n}")


@app.command("demo")
def demo(
    task: str = typer.Option("transfer_timeout_after_commit", "--task"),
    agent: str = typer.Option("naive", "--agent"),
) -> None:
    """Run one episode with a rich step log."""
    from paybench.agents import NaiveAgent, NullAgent, OracleAgent, RandomAgent
    from paybench.agents.base import Agent
    from paybench.runner.episode import run_episode
    from paybench.tasks.registry import get_task

    agents: dict[str, Agent] = {
        "oracle": OracleAgent(),
        "null": NullAgent(),
        "naive": NaiveAgent(),
        "random": RandomAgent(),
    }
    if agent not in agents:
        raise typer.Exit(1)
    ag = agents[agent]
    t = get_task(task)
    console.rule(f"[bold]{agent}[/bold] on [cyan]{task}[/cyan]")
    ep = run_episode(t, ag)
    for e in ep["case_log"]:
        ok = e["result"].get("ok")
        fault = e.get("fault")
        style = "green" if ok else "red"
        line = f"[{style}]#{e['step']} {e['tool']}[/{style}]"
        if fault:
            line += f" [yellow]fault={fault}[/yellow]"
        if not ok:
            err = e["result"].get("error") or {}
            line += f" {err.get('code')}: {err.get('message')}"
        console.print(line)
    console.print()
    console.print(
        f"success={ep['success']} partial={ep['partial']:.2f} "
        f"forbidden={ep['forbidden_hit']} modes={ep['failure_modes']}"
    )


@app.command("validate")
def validate() -> None:
    """Quick self-validation: Oracle=100%, Naive fails traps."""
    from paybench.agents import NaiveAgent, OracleAgent
    from paybench.runner.episode import run_episode
    from paybench.tasks.registry import all_tasks

    oracle_fail = [t.id for t in all_tasks() if not run_episode(t, OracleAgent())["success"]]
    naive_pass = [
        t.id
        for t in all_tasks()
        if t.category.value in ("adversarial", "faults") and run_episode(t, NaiveAgent())["success"]
    ]
    table = Table(title="Self-validation")
    table.add_column("check")
    table.add_column("result")
    table.add_row("Oracle 100%", "PASS" if not oracle_fail else f"FAIL {oracle_fail}")
    table.add_row(
        "Naive fails adv/faults",
        "PASS" if not naive_pass else f"FAIL {naive_pass}",
    )
    console.print(table)
    if oracle_fail or naive_pass:
        raise typer.Exit(1)


@app.command("play")
def play(task_id: str) -> None:
    """Interactive REPL: type tool calls as JSON."""
    from paybench.sim.tools import call_tool
    from paybench.tasks.graders import grade
    from paybench.tasks.registry import get_task, instantiate_world

    task = get_task(task_id)
    world = instantiate_world(task)
    console.print(task.instruction)
    console.print('Enter: {"tool": "name", "args": {...}}  or \'grade\' / \'quit\'')
    while True:
        try:
            line = console.input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line in ("quit", "exit"):
            break
        if line == "grade":
            g = grade(world, task)
            console.print(g)
            continue
        try:
            payload = json.loads(line)
            result = call_tool(world, payload["tool"], payload.get("args") or {})
            console.print_json(json.dumps(result))
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{exc}[/red]")


if __name__ == "__main__":
    app()
