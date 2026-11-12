# PayBench

**A deterministic benchmark for LLM agents that operate a payments back office.**

PayBench measures whether agents can look up transactions, issue refunds, move money, handle disputes and fraud, follow written policy, and recover from messy payment-API realities (timeouts with unknown outcomes, duplicates, rate limits, stale reads) — while resisting prompt injection.

> Status: under active construction. See `docs/PLAN.md`. Baseline agents and the simulator ship first; LLM numbers appear only after real runs (`TODO(real-run)`).

## Why this matters

1. Most agent benchmarks ignore **idempotency** and **"did it go through?"** ambiguity.
2. Graders inspect **final world state**, not prose — so scores are falsifiable.
3. An **Oracle** must score 100% and a **Naive** agent must fail every adversarial/fault trap.
4. Automatic **failure taxonomy** explains *why* agents fail (F1–F15).
5. Fully **deterministic**: same seed + actions → identical state hash, traces, and grades.

## Quickstart

```bash
pip install -e ".[dev]"
paybench --version
paybench demo --agent naive --task transfer_timeout_after_commit
paybench run --agent oracle --tasks core
```

## License

Apache-2.0
