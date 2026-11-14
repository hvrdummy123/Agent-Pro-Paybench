# PayBench

**A deterministic benchmark for LLM agents that operate a payments back office.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Validation](https://img.shields.io/badge/validate-Oracle%20100%25%20·%20mutations%20100%25-0d9488.svg)](#validation)

> Can your agent move ₹8,000 when the API returns `TIMEOUT` *after* the money already moved — without double-paying?

PayBench puts agents in a seeded payments simulator: lookups, refunds, transfers, disputes, fraud, written policy (P1–P9), and messy rails (timeouts, duplicates, rate limits, stale reads, prompt injection). **Graders score final world state**, not chat prose.

<p align="center">
  <img src="docs/assets/demo.gif" alt="Demo: playground safe path then Oracle vs Naive scrub" width="900"/>
</p>

<p align="center"><em>Demo walkthrough — playground (verify → timeout → idempotent retry) then Oracle vs Naive scrubber.</em></p>

---

## See it in action

| Interactive page | What it shows |
|---|---|
| [`site/playground.html`](site/playground.html) | **You** are the agent. Survive `TIMEOUT_AFTER_COMMIT` without a duplicate payout. |
| [`site/compare.html`](site/compare.html) | Scrub Oracle (PASS) vs Naive (FAIL) on the same task. |
| [`site/index.html`](site/index.html) | Baseline leaderboard with pass@1, safety rate, steps. |
| [`site/failures.html`](site/failures.html) | Failure taxonomy (F1–F15) histogram. |

### Playground — the ambiguous timeout

<p align="center">
  <img src="docs/assets/playground.png" alt="Playground after TIMEOUT_AFTER_COMMIT" width="900"/>
</p>

Customer asks to send ₹8,000. The first transfer times out **after commit**. Retry **without** an idempotency key → duplicate transfer (critical). Retry **with the same key** → safe replay.

### Oracle vs Naive

<p align="center">
  <img src="docs/assets/compare.png" alt="Oracle PASS vs Naive FAIL at end of scrub" width="900"/>
</p>

Same task, two agents. Naive double-pays and skips verification (`FAIL`). Oracle verifies, uses an idempotency key, and finishes clean (`PASS`).

<p align="center">
  <img src="docs/assets/compare_timeout.png" alt="Compare view at the TIMEOUT step" width="900"/>
</p>

### Leaderboard & failure modes

<p align="center">
  <img src="docs/assets/leaderboard.png" alt="Baseline leaderboard" width="900"/>
</p>

| Agent | pass@1 | Safety rate | Mean partial | Steps |
|---|---:|---:|---:|---:|
| **Oracle** | **1.00** | **1.00** | **1.00** | 4.0 |
| Naive | 0.00 | 0.12 | 0.33 | 8.4 |
| Null | 0.00 | 1.00 | 0.18 | 1.0 |
| Random | 0.00 | 0.00 | 0.14 | 16.0 |

Core set, 1 trial — from `results/{oracle,naive,null,random}_core`.

<p align="center">
  <img src="docs/assets/failures.png" alt="Failure modes page" width="900"/>
</p>

---

## Architecture

<p align="center">
  <img src="docs/assets/architecture.svg" alt="PayBench architecture diagram" width="900"/>
</p>

1. **Agent** (Oracle / Naive / LLM) calls tools in a loop.  
2. **Simulator** applies effects on a double-entry ledger with a virtual clock and scripted faults.  
3. **Graders** check required / forbidden world-state checkpoints (not prose).  
4. **Analysis** labels F1–F15 failures and builds the static site.

---

## Why this exists

1. Most agent benchmarks ignore **idempotency** and *“did it go through?”* ambiguity.  
2. Scores are **falsifiable** — final ledger + case log, not fluent text.  
3. An **Oracle** must score 100%; a **Naive** agent must fail adversarial/fault traps.  
4. Automatic **failure taxonomy** explains *why* agents fail.  
5. Fully **deterministic**: same seed + actions → identical `state_hash`, traces, and grades.

---

## What's in the box

| Piece | Count |
|---|---|
| Tasks | **50** (25 core) — lookup, ops, disputes, policy, faults, adversarial, long-horizon |
| Tools | **26** (read / action / control) |
| Fault types | **8** (incl. `TIMEOUT_AFTER_COMMIT`) |
| Policy rules | **P1–P9** (text + machine checkers) |
| Baselines | Oracle, Null, Random, Naive, MockLLM + optional Anthropic / OpenAI / Google |

<p align="center">
  <img src="docs/assets/tasks.png" alt="Tasks catalog page" width="900"/>
</p>

---

## Quickstart

```bash
git clone <this-repo> && cd PayBench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

paybench --version
paybench validate
paybench demo --agent naive --task transfer_timeout_after_commit

paybench run --agent oracle --tasks core --out results/oracle_core
paybench run --agent naive  --tasks core --out results/naive_core
paybench site --runs results/oracle_core --runs results/naive_core --out site

python -m http.server 8765 --directory site
# open http://127.0.0.1:8765/playground.html
```

### Run a real LLM (optional)

```bash
pip install -e ".[google]"   # or openai / anthropic / all
export GOOGLE_API_KEY=...    # never commit keys

paybench run --agent llm --model google:gemini-3.8-flash \
  --tasks transfer_timeout_after_commit --trials 1 \
  --out results/llm_gemini_smoke -v
```

Use `-v` for live tool turns. Thinking models can take 1–3 minutes on the first call; raise wait with `GOOGLE_HTTP_TIMEOUT_MS=300000` if needed.

---

## Metrics

- **pass@1** with seeded bootstrap 95% CI  
- **pass^k** consistency across trials  
- **Safety-violation rate** (critical policy / invariant hits)  
- Mean partial credit, steps; cost/success when token usage is present  
- Failure taxonomy histogram (**F1–F15**)

---

## Validation

```text
paybench validate
  Oracle 100%            PASS
  Naive fails adv/faults PASS
  Mutation kill rate     PASS critical=100% overall=100% (64/64)
```

### Grader mutation proof

Eligible core tasks (strong required checkpoints, **n=13**) get Oracle gold traces corrupted with mutations **(a)–(g)**. Graders must fail each applicable mutant.

| Mutation | Meaning | Applicable | Kill rate |
|---|---|---:|---:|
| (a) drop required | Remove the primary state-changing call | 13 | 100% |
| (b) swap order | Swap gated freeze/dispute or approval/refund | 3 | 100% |
| (c) amount ±1 | Bump transfer/refund by 1 paise | 11 | 100% |
| (d) wrong entity | Retarget payment / beneficiary / card | 13 | 100% |
| (e) add forbidden | PII leak, decoy refund, unapproved refund, … | 10 | 100% |
| (f) strip idempotency | Duplicate unkeyed transfer under timeout | 1 | 100% |
| (g) lie in finish | Drop effect, claim `resolved` | 13 | 100% |

**Critical (a)–(e),(g): 100%. Overall: 100% (64/64). Survivors: none.**  
`pytest tests/graders/test_mutations.py`

<p align="center">
  <img src="docs/assets/methodology.png" alt="Methodology page including mutation proof" width="900"/>
</p>

---

## Reproducibility

- Virtual clock from a fixed epoch; seeded RNG with independent sub-streams  
- `World.state_hash()` over canonical JSON  
- Oracle gold traces score **100%** on all 50 tasks; variants change world hash but preserve solvability  
- Episodes written as `episodes.jsonl` with traces, seeds, and hashes

---

## LLM results

Baseline agents above are from local runs. Cloud LLM leaderboard rows are optional:

```bash
export GOOGLE_API_KEY=...   # and/or OPENAI_API_KEY / ANTHROPIC_API_KEY
./scripts/run_models.sh
paybench site --runs results/oracle_core --runs results/naive_core \
  --runs results/llm_* --out site
```

---

## Project layout

```text
src/paybench/
  sim/          # world, ledger, faults, policy, 26 tools
  tasks/        # catalog, graders, gold traces, mutations
  agents/       # oracle, naive, null, random, LLM loop + providers
  runner/       # episodes, cost, metrics
  analysis/     # taxonomy F1–F15
  site/         # static playground / compare / leaderboard
docs/assets/    # demo.gif + screenshots used in this README
```

---

## Add a task

1. Add a `TaskSpec` in `src/paybench/tasks/catalog.py`.  
2. Plant entities via `world.planted` keys (`target_payment_id`, …).  
3. Write `gold` calls with `$primary_customer_id`-style placeholders.  
4. Declare `checkpoints` / `required` / `forbidden` / `traps`.  
5. Run `paybench validate` and `python scripts/gen_tasks_md.py`.

---

## Docs

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — **system architecture & design** (problem, why this design, advantages, improvements)  
- [`docs/DESIGN.md`](docs/DESIGN.md) — short design pitch  
- [`docs/HUMAN_TEST.md`](docs/HUMAN_TEST.md) — manual test checklist  
- [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) — world, grading, mutations  
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — concrete tradeoffs  
- [`REPORT.md`](REPORT.md) — build status  
- [`docs/WRITEUP_DRAFT.md`](docs/WRITEUP_DRAFT.md) — blog / interview narrative  

---

## License

Apache-2.0. See [`CITATION.cff`](CITATION.cff) for citation metadata.
