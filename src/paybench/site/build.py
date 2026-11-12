"""Build static leaderboard HTML from run directories."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from paybench.analysis.metrics import summarize
from paybench.analysis.taxonomy import classify
from paybench.tasks.registry import all_tasks

_BASELINES = frozenset({"oracle", "null", "random", "naive"})

_PAGE_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="PayBench leaderboard — deterministic fintech agent benchmark." />
  <title>{title}</title>
  <link rel="stylesheet" href="static/style.css" />
</head>
<body>
  <div class="wrap">
    <nav aria-label="Primary">
      <a href="index.html" {nav_home}>Leaderboard</a>
      <a href="failures.html" {nav_fail}>Failure modes</a>
      <a href="tasks.html" {nav_tasks}>Tasks</a>
      <a href="methodology.html" {nav_meth}>Methodology</a>
      <button type="button" class="btn-theme" id="theme-toggle" aria-label="Toggle color theme">Theme</button>
    </nav>
    {body}
  </div>
  <script>
  (function() {{
    var root = document.documentElement;
  try {{
      var stored = localStorage.getItem('paybench-theme');
      if (stored) root.setAttribute('data-theme', stored);
    }} catch (e) {{}}
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', function () {{
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try {{ localStorage.setItem('paybench-theme', next); }} catch (e) {{}}
    }});
  }})();
  {extra_js}
  </script>
</body>
</html>
"""

_SORT_TABLE_JS = """
document.querySelectorAll('table[data-sortable]').forEach(function (table) {
  table.querySelectorAll('th').forEach(function (th, col) {
    th.addEventListener('click', function () {
      var tbody = table.tBodies[0];
      var rows = Array.from(tbody.querySelectorAll('tr'));
      var asc = th.getAttribute('data-asc') !== 'true';
      th.setAttribute('data-asc', asc ? 'true' : 'false');
      rows.sort(function (a, b) {
        var av = a.children[col].getAttribute('data-sort') || a.children[col].textContent;
        var bv = b.children[col].getAttribute('data-sort') || b.children[col].textContent;
        var an = parseFloat(av), bn = parseFloat(bv);
        if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    });
  });
});
"""


def load_episodes_from_runs(run_dirs: list[Path]) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        path = run_dir / "episodes.jsonl"
        if not path.is_file():
            alt = run_dir if run_dir.name == "episodes.jsonl" else None
            if alt and run_dir.is_file():
                path = run_dir
            else:
                continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                episodes.append(json.loads(line))
    return episodes


def _shell(title: str, body: str, active: str, extra_js: str = "") -> str:
    def attr(page: str) -> str:
        return 'aria-current="page"' if page == active else ""

    return _PAGE_SHELL.format(
        title=title,
        body=body,
        nav_home=attr("home"),
        nav_fail=attr("fail"),
        nav_tasks=attr("tasks"),
        nav_meth=attr("meth"),
        extra_js=extra_js,
    )


def _pass_chart(agents: dict[str, Any], width: int = 900, height: int = 260) -> str:
    items = sorted(agents.items(), key=lambda x: -x[1]["pass_at_1"])
    if not items:
        return "<p class=\"lead\">No agent data to chart.</p>"
    margin = {"l": 48, "r": 16, "t": 24, "b": 64}
    inner_w = width - margin["l"] - margin["r"]
    inner_h = height - margin["t"] - margin["b"]
    bar_w = inner_w / max(len(items), 1) * 0.55
    parts = [
        f'<svg class="chart" role="img" aria-label="Pass at 1 by agent" '
        f'viewBox="0 0 {width} {height}" width="100%" height="{height}">'
    ]
    for i, (agent, row) in enumerate(items):
        x = margin["l"] + (i + 0.5) * (inner_w / len(items)) - bar_w / 2
        h = inner_h * row["pass_at_1"]
        y = margin["t"] + inner_h - h
        color = "var(--muted)" if agent in _BASELINES else "var(--accent)"
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}">'
            f"<title>{agent}: pass@1 {row['pass_at_1']:.2f}</title></rect>"
        )
        lo = row["pass_at_1_ci_low"]
        hi = row["pass_at_1_ci_high"]
        y_lo = margin["t"] + inner_h * (1 - lo)
        y_hi = margin["t"] + inner_h * (1 - hi)
        cx = x + bar_w / 2
        parts.append(
            f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{y_lo:.1f}" y2="{y_hi:.1f}" '
            f'stroke="var(--text)" stroke-width="2" />'
        )
        label = agent if len(agent) < 14 else agent[:12] + "…"
        parts.append(
            f'<text x="{cx:.1f}" y="{height - 20}" text-anchor="middle" '
            f'fill="var(--muted)" font-size="12">{label}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _taxonomy_bars(by_agent_tax: dict[str, dict[str, int]], width: int = 900, height: int = 320) -> str:
    codes = [f"F{i}" for i in range(1, 16)]
    agents = sorted(by_agent_tax.keys())
    if not agents:
        return "<p class=\"lead\">No failure taxonomy data yet.</p>"
    margin = {"l": 120, "r": 16, "t": 16, "b": 24}
    row_h = (height - margin["t"] - margin["b"]) / max(len(agents), 1)
    max_total = max(sum(by_agent_tax[a].values()) for a in agents) or 1
    inner_w = width - margin["l"] - margin["r"]
    palette = ["#0f766e", "#b45309", "#b91c1c", "#57534e", "#15803d", "#6366f1", "#a855f7"]
    parts = [
        f'<svg class="chart" role="img" aria-label="Taxonomy counts by agent" '
        f'viewBox="0 0 {width} {height}" width="100%" height="{height}">'
    ]
    for ri, agent in enumerate(agents):
        y = margin["t"] + ri * row_h + 4
        counts = by_agent_tax[agent]
        x: float = float(margin["l"])
        for ci, code in enumerate(codes):
            cnt = counts.get(code, 0)
            if cnt <= 0:
                continue
            bar_w = inner_w * (cnt / max_total)
            fill = palette[ci % len(palette)]
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{row_h - 8:.1f}" fill="{fill}">'
                f"<title>{agent} {code}: {cnt}</title></rect>"
            )
            x += bar_w
        parts.append(
            f'<text x="{margin["l"] - 8}" y="{y + row_h / 2:.1f}" text-anchor="end" '
            f'dominant-baseline="middle" fill="var(--text)" font-size="12">{agent}</text>'
        )
    parts.append("</svg>")
    legend = " ".join(f"<span class='tag'>{c}</span>" for c in codes if any(by_agent_tax[a].get(c, 0) for a in agents))
    return "\n".join(parts) + f"<p>{legend}</p>"


def _index_html(summary: dict[str, Any]) -> str:
    agents: dict[str, Any] = summary.get("agents") or {}
    k = summary.get("k", 3)
    rows: list[str] = []
    for agent, row in sorted(agents.items(), key=lambda x: -x[1]["pass_at_1"]):
        cls = ' class="baseline"' if agent in _BASELINES else ""
        pk = row.get(f"pass_pow_{k}")
        rows.append(
            f"<tr{cls}>"
            f"<td>{agent}</td>"
            f"<td data-sort=\"{row['pass_at_1']:.4f}\">{row['pass_at_1']:.2f}</td>"
            f"<td>{row['pass_at_1_ci_low']:.2f}–{row['pass_at_1_ci_high']:.2f}</td>"
            f"<td data-sort=\"{pk or 0:.4f}\">{(pk if pk is not None else 0):.2f}</td>"
            f"<td data-sort=\"{row['safety_rate']:.4f}\">{row['safety_rate']:.2f}</td>"
            f"<td data-sort=\"{row['mean_partial']:.4f}\">{row['mean_partial']:.2f}</td>"
            f"<td data-sort=\"{row['mean_steps']:.1f}\">{row['mean_steps']:.1f}</td>"
            "</tr>"
        )
    body = f"""
<h1>PayBench leaderboard</h1>
<p class="lead">Deterministic payments back-office benchmark. Baseline agents are shown in italics. Click column headers to sort.</p>
<div class="table-scroll">
<table data-sortable>
<thead><tr>
<th>Agent</th><th>pass@1</th><th>95% CI</th><th>pass^{k}</th><th>Safety rate</th><th>Mean partial</th><th>Steps</th>
</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
{_pass_chart(agents)}
<p class="lead">How to read: <strong>pass@1</strong> is mean success across trials; whiskers show a bootstrap 95% CI. <strong>Safety rate</strong> is the share of episodes with no critical policy violation.</p>
"""
    return _shell("PayBench — Leaderboard", body, "home", _SORT_TABLE_JS)


def _failures_html(episodes: list[dict[str, Any]]) -> str:
    by_agent: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ep in episodes:
        agent = str(ep.get("agent", "unknown"))
        for code in classify(ep):
            by_agent[agent][code] += 1
    body = f"""
<h1>Failure modes</h1>
<p class="lead">Stacked counts of taxonomy codes F1–F15 per agent (from recorded episodes only).</p>
{_taxonomy_bars(by_agent)}
"""
    return _shell("PayBench — Failure modes", body, "fail")


def _task_pass_rates(episodes: list[dict[str, Any]]) -> dict[str, float]:
    by_task: dict[str, list[bool]] = defaultdict(list)
    for ep in episodes:
        by_task[str(ep.get("task_id", ""))].append(bool(ep.get("success")))
    return {tid: (sum(v) / len(v) if v else 0.0) for tid, v in by_task.items()}


def _tasks_html(episodes: list[dict[str, Any]]) -> str:
    rates = _task_pass_rates(episodes)
    cards: list[str] = []
    for t in all_tasks():
        rate = rates.get(t.id, 0.0)
        core = "core" if t.core else "ext"
        trap = (t.traps[0] if t.traps else "—").replace("<", "&lt;")
        cards.append(
            f"<article class='task-card'><h2 class='mono'>{t.id}</h2>"
            f"<p><span class='tag'>{t.category.value}</span> "
            f"<span class='tag'>{t.difficulty.value}</span> "
            f"<span class='tag'>{core}</span></p>"
            f"<p data-sort=\"{rate:.4f}\">Pass rate (all runs): <strong>{rate:.0%}</strong></p>"
            f"<p class='lead'>{trap}</p></article>"
        )
    body = f"""
<h1>Tasks</h1>
<p class="lead">{len(cards)} benchmark tasks from the registry.</p>
<div class="task-grid">
{''.join(cards)}
</div>
"""
    return _shell("PayBench — Tasks", body, "tasks")


def _methodology_html(repo_root: Path) -> str:
    meth = repo_root / "docs" / "METHODOLOGY.md"
    if meth.is_file():
        text = meth.read_text(encoding="utf-8")
    else:
        text = "# Methodology\n\nPayBench grades agents on deterministic simulator episodes.\n"
    # Minimal markdown → HTML (headings and paragraphs only)
    blocks: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            blocks.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            continue
        elif line.strip() == "":
            blocks.append("")
        elif line.startswith("- "):
            blocks.append(f"<li>{line[2:]}</li>")
        else:
            blocks.append(f"<p>{line}</p>")
    html_body = "\n".join(blocks)
    body = f"""
<h1>Methodology</h1>
<div class="methodology">
{html_body}
</div>
"""
    return _shell("PayBench — Methodology", body, "meth")


def build_site(run_dirs: list[Path], out_dir: Path, *, repo_root: Path | None = None) -> None:
    """Generate static site under ``out_dir``."""
    root = repo_root or Path.cwd()
    episodes = load_episodes_from_runs(run_dirs)
    summary = summarize(episodes)
    out_dir.mkdir(parents=True, exist_ok=True)
    static_src = Path(__file__).resolve().parent / "static"
    static_dst = out_dir / "static"
    static_dst.mkdir(parents=True, exist_ok=True)
    for css in static_src.glob("*.css"):
        shutil.copy2(css, static_dst / css.name)
    pages = {
        "index.html": _index_html(summary),
        "failures.html": _failures_html(episodes),
        "tasks.html": _tasks_html(episodes),
        "methodology.html": _methodology_html(root),
    }
    for name, content in pages.items():
        (out_dir / name).write_text(content, encoding="utf-8")
    meta = {
        "n_episodes": len(episodes),
        "run_dirs": [str(p) for p in run_dirs],
        "agents": list((summary.get("agents") or {}).keys()),
    }
    (out_dir / "summary.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
