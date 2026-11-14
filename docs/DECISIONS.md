# Decisions

- **Package name `paybench`**: PyPI showed no existing distribution; keep import name `paybench`.
- **Epoch `2026-01-01T00:00:00Z`**: fixed virtual clock start per task for determinism.
- **Money as int minor units only**: no floats; `Money` rejects float inputs at construction.
- **FX rounding**: banker's round (half-even) to nearest minor unit when converting via rates.
- **Default tool virtual latency**: 2 seconds per tool call unless overridden.
- **Ledger balances derived**: account.balance never stored independently; always sum of entries.
- **Policy enforcement split**: tools block only hard validations; policy engine grades soft violations.
- **RNG sub-streams**: named children via SHA-256(seed||name) so subsystem draws stay independent.
- **Git branch `main`**: rename from default after init (no git config changes).
- **Master prompt kept as `paybench_agent_prompt.md`**: reference for build; not published as package data.
- **Coverage omit cli/__main__ until harness lands**: keep overall gate at 80%; sim modules still heavily tested.
- **P9 detector uses log order, not step ids**: avoids false negatives when synthetic log steps are inserted in tests.
- **Optional LLM providers omitted from coverage**: anthropic/openai/google adapters need live SDKs; MockLLM is tested.
- **P7 injection narrowed to sink match**: avoid false positives on legitimate transfers when notes mention "transfer".
- **Mutation suite**: kill-rate targets measured on *eligible* core tasks (strong required checkpoints), not every soft-required lookup. Weak mutators (ungated order-swap; PII text that does not match planted email/DOB) were tightened so critical kill rate is falsifiable at 100%.
- **Cut deferred**: richer per-episode HTML pages; packaging clean-venv; mutation eligibility for the full 50-task catalog.
- **Playground is client-side JS**: static host can’t run the Python sim in-browser; playground faithfully models TIMEOUT_AFTER_COMMIT + idempotency for the headline task only.
- **Compare page embeds live Oracle/Naive traces** at site-build time so the scrubber always shows real harness output.
