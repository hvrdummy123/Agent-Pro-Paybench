# PayBench Build Plan

Portfolio-grade fintech agent benchmark: deterministic payments world, ~50 graded tasks, fault injection, failure taxonomy, leaderboard site.

## Milestones

- [x] **M1 Foundations** — repo, pyproject, CI skeleton, Money, Clock, Rng, ids, World, ledger + tests
- [x] **M2 Tools and policy** — all tools, idempotency, policy text + rule engine, unit/property tests
- [x] **M3 Faults** — FaultPlan, injector, profiles (clean/flaky/hostile), fault tests
- [x] **M4 Tasks and graders** — schema, builders, 3 seed tasks then 50 total, gold solutions, graders, docs/TASKS.md
- [x] **M5 Baselines and self-validation** — Oracle/Null/Random/Naive, mutation/trap/variant tests; gate: Oracle=100%
- [x] **M6 Harness and providers** — LLM loop, Anthropic/OpenAI/Google/Mock, runner, cost guard (resume/replay partial)
- [x] **M7 Analysis** — metrics, bootstrap CIs, taxonomy classifier, report command
- [x] **M8 Site and demo** — static leaderboard, `paybench demo` (per-episode HTML trace viewer still thin)
- [x] **M9 Packaging and docs** — README, DESIGN, METHODOLOGY, TAXONOMY, CITATION, scripts, wheel build
- [x] **M10 Final verification** — suite green, baseline site, REPORT.md; real-model smoke skipped (no keys)

## Cut line

If budget-constrained: reduce to 25 `core` tasks with every category represented. Never cut self-validation, determinism, or idempotency/fault semantics.

## Day mapping (D1–D7)

| Day | Focus | Milestones |
|-----|-------|------------|
| D1 | Design world + task spec | PLAN, DESIGN, DECISIONS; M1 start |
| D2 | Simulator (seeded, deterministic) | M1–M3 |
| D3 | 30–50 tasks + graders | M4–M5 |
| D4 | Agent harness + first model | M6 |
| D5 | Multi-model runs + cost/latency/failures | M6–M7 |
| D6 | Taxonomy, leaderboard, pip package | M7–M9 |
| D7 | Writeup + demo | M8–M10 |
