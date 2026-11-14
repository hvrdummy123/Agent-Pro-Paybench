# PayBench methodology

PayBench scores agents in a **deterministic, in-process payments simulator**. Each episode is a fresh world seeded from the task specification; the agent may only change state through registered tools.

## World and tools

The simulator models customers, accounts, cards, payments, transfers, disputes, approvals, and messages. Tools mirror back-office APIs: lookups, refunds, transfers, card controls, disputes, policy retrieval, and `finish` with an explicit outcome.

## Fault injection

Tasks may attach fault profiles (`clean`, `flaky`, `hostile`) that inject timeouts, stale reads, rate limits, and duplicate deliveries. Fault events are recorded in the case log for graders and the failure taxonomy.

## Policy and grading

Written policy (`get_policy`) is machine-checked post hoc (`P1`–`P9` plus ledger invariants). Success requires all **required** checkpoints, no **forbidden** conditions, honest `finish`, and no critical violations. Partial credit is the fraction of checkpoints passed.

## Metrics

- **pass@1**: mean success over trials, with a seeded 95% bootstrap CI (1,000 resamples).
- **pass^k**: share of tasks solved on all *k* trials (default *k*=3).
- **Safety rate**: episodes with no critical policy violation.
- **Mean partial**: average checkpoint fraction.

## Determinism and validation

Oracle replays gold traces (expect 100% pass). Null, Random, and Naive baselines anchor the floor and trap coverage. Property tests and grader mutation checks guard scoring drift.

### Grader mutation tests (real run)

On **13 eligible core tasks** (required set includes a strong state checkpoint), gold traces are corrupted with mutations (a)–(g). Applicable mutants: **64**. Kill rates from `paybench validate` / `pytest tests/graders/test_mutations.py`:

- **Critical (a)–(e),(g): 100%**
- **Overall (incl. f): 100% (64/64)**
- **Survivors: none**

Mutators that cannot apply to a task (e.g. order-swap without an ordering gate) are marked N/A and excluded from the rate.

## Reproducibility

Each run writes `episodes.jsonl` with full traces, `prompt_version`, seeds, and `state_hash`. Re-execute tool calls on a fresh world to verify the hash matches.
