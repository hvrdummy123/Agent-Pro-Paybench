# Human test checklist

Run after a fresh clone. Check each box manually.

1. [ ] Fresh clone → `uv sync` or `pip install -e ".[dev]"` → `pytest -n auto` passes.
2. [ ] `paybench demo --agent naive --task transfer_timeout_after_commit`: duplicate transfer + violation are visible.
3. [ ] `paybench demo --agent oracle` on five tasks (mix categories): clean successes.
4. [ ] Read 10 random tasks via `paybench show-task <id>`: instructions clear and policy-sufficient.
5. [ ] `paybench play transfer_timeout_after_commit`: type JSON tool calls; try an alternate valid solution (same key retry vs list_transfers); note any false negatives.
6. [ ] Open `site/index.html` at desktop and ~360px widths, light and dark: layout, contrast, sorting.
7. [ ] `TODO(real-run)`: run a real model on 3 tasks; check failure labels match the trace.
8. [ ] `python -m build` → install wheel in a clean venv → `paybench --version`, `list-tasks`, `validate`.
9. [ ] Spot check: no secrets, no absolute paths, no bare `TODO` outside `TODO(real-run)`.
