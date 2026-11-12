# PayBench writeup draft (~1,500 words skeleton)

## Hook: the ambiguous timeout

The first `create_transfer` returns `TIMEOUT`. Did the ₹8,000 leave the account? In real payment APIs the answer is often *maybe*. PayBench makes that ambiguity a first-class trap: the effect committed, the client saw failure, and a naive retry without an idempotency key doubles the money movement.

## Why existing agent benchmarks miss this

Most suites grade fluent text or single-shot tool accuracy. They rarely model replica lag, rate limits, partial commits, or policy that the tools themselves do not hard-enforce. PayBench grades **final ledger state** and a case log — not prose.

## The world and its traps

A seeded double-entry ledger, virtual clock, 26 tools, policy P1–P9, and fault profiles (`clean` / `flaky` / `hostile`). Untrusted `memo` and merchant `notes` fields plant injections. Fifty tasks span lookup through long-horizon fraud rings.

## How grading works

Checkpoints over world state + case log; forbidden conditions; honesty of `finish`; critical policy/invariant violations zero the episode. Partial credit remains for analysis.

## Proving the benchmark is sound

- OracleAgent = **100%** on all 50 tasks (and variants).
- NaiveAgent fails **every** adversarial and fault task (duplicate transfers, injection following, skipped verification).
- NullAgent fails action-requiring tasks.
- RandomAgent success ≤ 5%.
- Taxonomy detectors have unit tests per F-code.

## Results

Baseline (core, 1 trial): Oracle pass@1 = 1.00; Naive = 0.00; Null = 0.00.

LLM leaderboard: `TODO(real-run)`.

## What broke while building this

Real issues from this build (see also `docs/DECISIONS.md`):

- Early transfer gold used amounts larger than seeded balances — Oracle failed until opening balances were raised.
- P7 injection detection was too broad and flagged legitimate rent transfers when merchant notes mentioned *any* transfer; detectors were narrowed to injected sinks (99-ZZ / sanctions).
- P9 unsafe-retry detection keyed off step ids, which broke when synthetic log entries used out-of-order steps; switched to log order.
- Catalog line-length noise forced per-file ruff ignores for generated-style task specs.

## Limitations and next steps

Simulated rails, scripted customer, stylized policy. Next: full model sweep via `scripts/run_models.sh`, mutation-test expansion, PyPI publish, demo GIF.
