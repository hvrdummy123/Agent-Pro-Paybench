"""PayBench CLI (stub grows across milestones)."""

from __future__ import annotations

import typer

from paybench import __version__

app = typer.Typer(
    name="paybench",
    help="PayBench: deterministic fintech agent benchmark.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.command("list-tasks")
def list_tasks(
    category: str | None = typer.Option(None, "--category"),
    core: bool = typer.Option(False, "--core"),
) -> None:
    """List benchmark tasks (available after M4)."""
    _ = (category, core)
    typer.echo("No tasks registered yet (M4).")


if __name__ == "__main__":
    app()
