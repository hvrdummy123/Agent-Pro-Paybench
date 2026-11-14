# PayBench REPORT

Built: 2026-11-12. Factual status after local autonomous build.

## What was built

- **Simulator** (`src/paybench/sim/`): Money, Clock, Rng, ids, double-entry ledger, World hashing/snapshots, 26 tools, policy.md + P1–P9 checkers, 8 fault types with profiles.
- **Tasks**: **50** total / **25** core across all 7 categories; gold traces; state-based graders.
- **Agents**: Oracle, Null, Random, Naive, MockLLM loop; Anthropic/OpenAI/Google adapters (optional extras).
- **Runner / analysis**: episode runner, cost/pricing placeholders, taxonomy F1–F15, metrics (pass@1, pass^k, bootstrap CI), report + static site.
- **CLI**: `list-tasks`, `show-task`, `run`, `demo`, `validate`, `play`, `report`, `site`.
- **Packaging**: wheel+sdist via hatchling (`dist/paybench-0.1.0-*.whl`).

## Test results (real commands)

```text
ruff check src tests          → All checks passed
mypy --strict src/            → Success: no issues found in 52 source files
pytest -n auto --cov=paybench --cov-fail-under=80
  → Required test coverage of 80% reached. Total coverage: 83.43%
paybench validate
  → Oracle 100% PASS
  → Naive fails adv/faults PASS
python -m build               → paybench-0.1.0 sdist + wheel
```

Baseline core runs (1 trial):

| Agent | pass |
|---|---|
| Oracle | 25/25 |
| Naive | 0/25 |
| Null | 0/25 |

Site built at `site/` from those runs.

## Real-model run status

**Skipped** — no `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` in the environment.

Commands to run:

```bash
pip install -e ".[all]"
export ANTHROPIC_API_KEY=...
paybench run --agent llm --model anthropic:claude-haiku-4-5-20251001 \
  --tasks core --trials 1 --max-cost-usd 3 --out results/smoke_anthropic
./scripts/run_models.sh
```

## Decisions / deviations

See `docs/DECISIONS.md`. Notable:

- Optional provider modules omitted from coverage totals (require live SDKs/keys).
- Grader mutation suite (a–g) is automated on eligible core tasks: **critical=100%, overall=100% (64/64)**, survivors none — see README validation section and `tests/graders/test_mutations.py`.
- Full packaging clean-venv install test and deeper per-episode HTML trace pages remain partial vs the master prompt (leaderboard + playground + compare + failures + tasks + methodology ship).

## Known limitations

- Scripted customer; stylized policy; simulated rails only.
- Pricing.yaml values are placeholders (`# VERIFY`).
- LLM leaderboard numbers intentionally absent (`TODO(real-run)`).

## Exact next steps for you

1. Run `docs/HUMAN_TEST.md`.
2. Set API keys and run `./scripts/run_models.sh`.
3. Publish wheel to PyPI; deploy `site/` to GitHub Pages.
4. ~~Demo GIF~~ — `docs/assets/demo.gif` (playground safe path + Oracle vs Naive scrub).
5. Extend mutation eligibility beyond strong-required core tasks; deepen per-episode HTML trace viewer.
