# PayBench

**A deterministic benchmark for LLM agents that operate a payments back office.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

PayBench measures whether agents can look up transactions, issue refunds, move money, handle disputes and fraud, follow written policy, and recover from messy payment-API realities — timeouts with unknown outcomes, duplicates, rate limits, stale reads — while resisting prompt injection.

## Why this matters

1. Most agent benchmarks ignore **idempotency** and **"did it go through?"** ambiguity.
2. Graders inspect **final world state**, not prose — scores are falsifiable.
3. An **Oracle** must score 100%; a **Naive** agent must fail every adversarial/fault trap.
4. Automatic **failure taxonomy** (F1–F15) explains *why* agents fail.
5. Fully **deterministic**: same seed + actions → identical state hash, traces, and grades.

## Quickstart

```bash
pip install -e ".[dev]"
paybench --version
paybench demo --agent naive --task transfer_timeout_after_commit
paybench validate
paybench run --agent oracle --tasks core --out results/oracle_core
paybench run --agent naive --tasks core --out results/naive_core
paybench site --runs results/oracle_core --runs results/naive_core --out site
```

Open the interactive demos:

- `site/playground.html` — **you** are the agent; survive `TIMEOUT_AFTER_COMMIT` without double-paying
- `site/compare.html` — scrub Oracle vs Naive on the same task
- `site/index.html` — baseline leaderboard

## What's in the benchmark

| Piece | Count |
|---|---|
| Tasks | 50 (25 core) across lookup, ops, disputes, policy, faults, adversarial, long-horizon |
| Tools | 26 (read / action / control) |
| Fault types | 8 (incl. `TIMEOUT_AFTER_COMMIT`) |
| Policy rules | P1–P9 (text + machine checkers) |
| Baselines | Oracle, Null, Random, Naive, MockLLM |

Headline trap: first `create_transfer` returns `TIMEOUT` **after** commit. Retry without an idempotency key → duplicate transfer (critical).

## Metrics

- **pass@1** with seeded bootstrap 95% CI
- **pass^k** consistency across trials
- **Safety-violation rate** (critical policy/invariant hits)
- Mean partial credit, steps; cost/success when token usage is present
- Failure taxonomy histogram (F1–F15)

## Reproducibility

- Virtual clock from fixed epoch; seeded RNG with independent sub-streams
- `World.state_hash()` over canonical JSON
- Oracle gold traces score 100% on all 50 tasks; variants change world hash but preserve solvability

## Validation (real local runs)

```text
paybench validate
  Oracle 100%            PASS
  Naive fails adv/faults PASS
```

Core baseline run: Oracle **25/25**, Naive **0/25**, Null **0/25**.

## LLM results

`TODO(real-run)` — no API keys were present during this build. To run:

```bash
export ANTHROPIC_API_KEY=...   # and/or OPENAI_API_KEY / GOOGLE_API_KEY
pip install -e ".[anthropic]"  # or openai / google / all
./scripts/run_models.sh
```

## Add a task

1. Add a `TaskSpec` in `src/paybench/tasks/catalog.py` (or a new module imported by the registry).
2. Plant entities via `world.planted` keys (`target_payment_id`, etc.).
3. Write `gold` calls using `$primary_customer_id` placeholders.
4. Declare `checkpoints` / `required` / `forbidden` / `traps`.
5. Run `paybench validate` and `python scripts/gen_tasks_md.py`.

## License

Apache-2.0. See `CITATION.cff` for citation metadata.
