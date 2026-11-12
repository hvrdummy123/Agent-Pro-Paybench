"""Markdown report rendering."""

from __future__ import annotations

from typing import Any


def render_markdown(summary: dict[str, Any]) -> str:
    """Render a summary table from :func:`summarize` output."""
    agents: dict[str, Any] = summary.get("agents") or {}
    k = int(summary.get("k") or 3)
    lines = [
        "# PayBench run summary",
        "",
        f"Episodes: **{summary.get('n_episodes', 0)}**",
        "",
        "| Agent | pass@1 | 95% CI | pass^"
        + str(k)
        + " | safety rate | mean partial | mean steps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for agent, row in sorted(agents.items()):
        ci = f"{row['pass_at_1_ci_low']:.2f}–{row['pass_at_1_ci_high']:.2f}"
        pk = row.get(f"pass_pow_{k}")
        pk_s = f"{pk:.2f}" if pk is not None else "—"
        lines.append(
            f"| {agent} | {row['pass_at_1']:.2f} | {ci} | {pk_s} | "
            f"{row['safety_rate']:.2f} | {row['mean_partial']:.2f} | {row['mean_steps']:.1f} |"
        )
    tax = summary.get("taxonomy_counts") or {}
    if tax:
        lines.extend(["", "## Failure taxonomy (episode counts)", ""])
        for code, count in sorted(tax.items()):
            lines.append(f"- **{code}**: {count}")
    lines.append("")
    return "\n".join(lines)
