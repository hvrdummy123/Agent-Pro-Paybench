#!/usr/bin/env python3
"""Generate docs/TASKS.md from the task registry."""

from __future__ import annotations

from pathlib import Path

from paybench.tasks.registry import all_tasks


def main() -> None:
    lines = [
        "# PayBench Tasks",
        "",
        f"Total: **{len(list(all_tasks()))}** tasks "
        f"({sum(1 for t in all_tasks() if t.core)} core).",
        "",
        "| ID | Category | Diff | Core | Title | Required | Traps |",
        "|---|---|---|---|---|---|---|",
    ]
    for t in all_tasks():
        core = "★" if t.core else ""
        traps = "; ".join(t.traps)[:80]
        req = ", ".join(t.required)[:60]
        lines.append(
            f"| `{t.id}` | {t.category.value} | {t.difficulty.value} | {core} | "
            f"{t.title} | {req} | {traps} |"
        )
    out = Path(__file__).resolve().parents[1] / "docs" / "TASKS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
