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
    model: str | None = typer.Option(None, "--model", help="provider:model_id for --agent llm"),
    max_cost_usd: float | None = typer.Option(None, "--max-cost-usd"),
    out: Path | None = typer.Option(None, "--out"),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print per-turn LLM/tool progress"
    ),
) -> None:
    """Run agents on tasks and write JSONL results."""
    from paybench.agents import NaiveAgent, NullAgent, OracleAgent, RandomAgent
    from paybench.agents.base import Agent
    from paybench.runner.cost import compute_cost_usd
    from paybench.runner.episode import run_episode
    from paybench.tasks.registry import all_tasks, core_tasks, get_task

    if agent == "llm":
        from paybench.agents.llm_loop import LLMAgent
        from paybench.agents.providers import build_provider

        if not model:
            console.print("[red]--model provider:id required for --agent llm[/red]")
            raise typer.Exit(1)
        try:
            provider = build_provider(model)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from exc
        ag: Agent = LLMAgent(provider=provider, model_key=model)
    else:
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
    spend = 0.0
    total = len(task_list) * trials * variants
    console.print(
        f"Running {total} episode(s) → {path}"
        + (" (verbose)" if verbose else " (add -v for live turns)")
    )
    with path.open("w", encoding="utf-8") as f:
        for t in task_list:
            for trial in range(trials):
                for variant in range(variants):
                    console.print(
                        f"[{n + 1}/{total}] {t.id} trial={trial} variant={variant} …",
                        end="\n",
                    )
                    ep = run_episode(
                        t, ag, variant=variant, trial=trial, verbose=verbose
                    )
                    if model:
                        tin = int(ep.get("tokens_in") or 0)
                        tout = int(ep.get("tokens_out") or 0)
                        cost, _ = compute_cost_usd(model, tokens_in=tin, tokens_out=tout)
                        ep["cost_usd"] = cost
                        spend += cost
                    f.write(json.dumps(ep) + "\n")
                    f.flush()
                    n += 1
                    n_ok += int(ep["success"])
                    console.print(
                        f"  → {'PASS' if ep['success'] else 'FAIL'}"
                        f" steps={ep.get('steps')} "
                        f"err={ep.get('agent_error') or '—'}"
                    )
                    # Treat 0/None as "no guard". A zero cap used to abort after the
                    # first episode whenever priced cost stayed $0 (common for free tiers).
                    if (
                        max_cost_usd is not None
                        and max_cost_usd > 0
                        and spend >= max_cost_usd
                    ):
                        console.print(
                            f"[yellow]Cost guard hit (${spend:.4f} >= {max_cost_usd})[/yellow]"
                        )
                        console.print(f"Wrote {path}  pass={n_ok}/{n}")
                        raise typer.Exit(2)
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
    """Self-validation: Oracle=100%, Naive fails traps, grader mutation kill rates."""
    from paybench.agents import NaiveAgent, OracleAgent
    from paybench.runner.episode import run_episode
    from paybench.tasks.mutations import run_mutation_suite
    from paybench.tasks.registry import all_tasks, core_tasks

    oracle_fail = [t.id for t in all_tasks() if not run_episode(t, OracleAgent())["success"]]
    naive_pass = [
        t.id
        for t in all_tasks()
        if t.category.value in ("adversarial", "faults") and run_episode(t, NaiveAgent())["success"]
    ]
    mut = run_mutation_suite(core_tasks())
    mut_ok = mut["critical_kill_rate"] >= 1.0 and mut["overall_kill_rate"] >= 0.95
    table = Table(title="Self-validation")
    table.add_column("check")
    table.add_column("result")
    table.add_row("Oracle 100%", "PASS" if not oracle_fail else f"FAIL {oracle_fail}")
    table.add_row(
        "Naive fails adv/faults",
        "PASS" if not naive_pass else f"FAIL {naive_pass}",
    )
    table.add_row(
        "Mutation kill rate",
        (
            f"PASS critical={mut['critical_kill_rate']:.0%} "
            f"overall={mut['overall_kill_rate']:.0%} "
            f"({mut['n_killed']}/{mut['n_applicable']})"
            if mut_ok
            else f"FAIL survivors={mut['survivors'][:5]}"
        ),
    )
    console.print(table)
    if oracle_fail or naive_pass or not mut_ok:
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


@app.command("report")
def report_cmd(
    run_dir: Path,
    k: int = typer.Option(3, "--k", help="Trials for pass^k metric."),
) -> None:
    """Summarize a run directory and print a Markdown table."""
    import json

    from paybench.analysis.metrics import summarize
    from paybench.analysis.report import render_markdown
    from paybench.runner.cost import has_placeholder_prices

    path = run_dir / "episodes.jsonl"
    if not path.is_file():
        console.print(f"[red]Missing {path}[/red]")
        raise typer.Exit(1)
    lines = path.read_text(encoding="utf-8").splitlines()
    episodes = [json.loads(line) for line in lines if line.strip()]
    summary = summarize(episodes, k=k)
    md = render_markdown(summary)
    out_md = run_dir / "summary.md"
    out_json = run_dir / "summary.json"
    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if has_placeholder_prices():
        console.print(
            "[bold yellow]WARNING:[/bold yellow] pricing.yaml still contains # VERIFY placeholders."
        )
    console.print(md)
    console.print(f"\nWrote {out_md} and {out_json}")


@app.command("site")
def site_cmd(
    runs: list[Path] = typer.Option(..., "--runs", help="Run dirs containing episodes.jsonl"),
    out: Path = typer.Option(Path("site"), "--out", help="Output directory for static HTML"),
) -> None:
    """Build static leaderboard site from one or more runs."""
    from paybench.site.build import build_site

    missing = [p for p in runs if not (p / "episodes.jsonl").is_file()]
    if missing:
        console.print(f"[red]No episodes.jsonl in: {', '.join(str(p) for p in missing)}[/red]")
        raise typer.Exit(1)
    build_site(runs, out)
    console.print(f"Wrote site to {out.resolve()}")


if __name__ == "__main__":
    app()
