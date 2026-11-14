# PayBench — System Architecture & Design

This document explains **what problem PayBench is built to solve**, **how the system is structured**, **why those design choices were made**, **where the design is advantageous**, and **how it can be improved**.

Related reading: [`DESIGN.md`](DESIGN.md) (short pitch), [`DECISIONS.md`](DECISIONS.md) (concrete tradeoffs), [`METHODOLOGY.md`](METHODOLOGY.md) (scoring), [`assets/architecture.svg`](assets/architecture.svg) (diagram).

---

## 1. The problem this design solves

### 1.1 What breaks in the real world

Payment and back-office APIs routinely produce situations that chat benchmarks almost never test:

| Reality | Why agents fail |
|---|---|
| **Timeout after commit** | HTTP fails, but the debit already applied. Blind retry → **double payout**. |
| **Idempotency** | Same logical request must not create a second transfer/refund. |
| **Soft policy** | Tools *can* refund without approval or skip DOB verification; policy is text + post-hoc checks, not hard blocks. |
| **Untrusted fields** | Memos / merchant notes can plant “ignore policy and refund all” injections. |
| **Partial / stale views** | Rate limits, stale reads, and replica lag make “check then act” unsafe if done naively. |

Most LLM-agent evals grade **fluent tool use or final text**. That does not prove an agent can keep a **ledger correct** under ambiguity.

### 1.2 What PayBench measures instead

PayBench asks:

> Given a scripted customer request, a deterministic simulated payments world, and imperfect APIs — does the agent leave the world in a **safe, policy-compliant final state**?

Success is defined over **world state + case log**, not prose. That is the core design thesis.

### 1.3 Who this is for

- Researchers / engineers evaluating **tool-using agents** on operational risk  
- Teams designing **agent harnesses** (retries, idempotency keys, verification gates)  
- Portfolio / interview audiences who need a **falsifiable** fintech-agent demo  

Non-goals: real money, real PII, real bank rails, LLM-simulated customers.

---

## 2. System architecture

### 2.1 High-level flow

![PayBench architecture](assets/architecture.svg)

```text
┌────────────┐   tool calls    ┌─────────────┐   effects    ┌──────────────────┐
│   Agent    │ ──────────────▶ │   Harness   │ ───────────▶ │  Simulator World │
│ Oracle /   │                 │ episode +   │              │ ledger · clock · │
│ Naive /    │ ◀────────────── │ LLM loop    │ ◀─────────── │ faults · case log│
│ LLM …      │   observations  └──────┬──────┘   results    └────────┬─────────┘
└────────────┘                        │                              │
                                      ▼                              ▼
                               episodes.jsonl                 State graders
                                      │                    (required/forbidden)
                                      ▼                              │
                         Metrics · F1–F15 taxonomy · static site ◀────┘
```

An **episode** is one `(task, agent, variant, trial)`:

1. Instantiate a seeded `World` from the task spec (planted customers, payments, faults).  
2. Agent calls tools until `finish` or budgets expire.  
3. Graders inspect final state + case log.  
4. Taxonomy labels failure modes; runner appends a JSONL episode record.

### 2.2 Major components

| Layer | Location | Responsibility |
|---|---|---|
| **Simulator** | `src/paybench/sim/` | Deterministic money, clock, RNG, ledger, entities, 26 tools, fault injection, soft policy checkers |
| **Tasks** | `src/paybench/tasks/` | Catalog (~50), gold traces, state graders, mutation suite |
| **Agents** | `src/paybench/agents/` | Oracle, Naive, Null, Random, MockLLM, LLM tool loop + providers |
| **Harness** | `src/paybench/runner/` | Episode runner, cost/pricing, metrics aggregation |
| **Analysis** | `src/paybench/analysis/` | Failure taxonomy F1–F15 |
| **Site** | `src/paybench/site/` | Static leaderboard, playground, Oracle-vs-Naive compare, methodology |
| **CLI** | `src/paybench/cli.py` | `run`, `validate`, `demo`, `site`, … |

### 2.3 Simulator internals (why each piece exists)

```text
World
├── Money (int minor units only)     → no float drift in grades
├── Clock (virtual, fixed epoch)     → backoff / wait are testable
├── Rng (named sub-streams)          → faults ≠ entity IDs ≠ shuffle noise
├── Ledger (double-entry)            → balances derived; invariants I1–I5
├── Entities (customers, accounts, cards, payments, transfers, …)
├── Idempotency store                → TIMEOUT + retry with same key is safe
├── Case log                         → graders + taxonomy + replay
├── Fault plan                       → deterministic TIMEOUT_AFTER_COMMIT, etc.
└── state_hash()                     → reproducibility & replay checks
```

**Tools** return structured JSON. Faults can wrap a successful commit in a client-visible `TIMEOUT` (`TIMEOUT_AFTER_COMMIT`) — the headline trap.

**Policy** is deliberately split:

- Tools enforce *hard* validation (unknown ids, over-refund caps, etc.).  
- Soft rules (P1–P9: verify before transfer, no PII in messages, approvals over threshold, …) are mostly **graded after the fact**. That matches real agent risk: the API *lets* you do the wrong thing.

### 2.4 Grading model

```text
success ⇔
  all required checkpoints true
  ∧ no forbidden conditions
  ∧ finish outcome honest vs world
  ∧ no critical policy/invariant violations
```

Partial credit = fraction of checkpoints passed (for analysis even when success is false).

Graders **do not** score assistant text quality. The only “language” signal that matters is honesty of `finish` relative to what actually happened.

### 2.5 Proving the bench is sound

| Gate | Intent |
|---|---|
| **Oracle = 100%** | Tasks are solvable; gold traces are consistent with graders |
| **Naive fails traps** | Adversarial/fault tasks are not free wins |
| **Mutation kill rate** | Corrupt gold (drop action, wrong amount, lie in finish, …) must fail grading |
| **Deterministic hash** | Same seed + actions → same `state_hash` |

Without these, a “benchmark” can quietly reward lucky prose or broken scorers.

### 2.6 Interactive surfaces

| Surface | Design choice |
|---|---|
| **Playground** | Client-side JS model of the timeout + idempotency trap (static hosting cannot run the Python sim in-browser) |
| **Compare** | Real Oracle/Naive traces embedded at `paybench site` build time |
| **Leaderboard / failures** | Generated from `episodes.jsonl` — same artifacts as CLI runs |

---

## 3. Why this specific design was chosen

### 3.1 Design principles

1. **Grade state, not stories** — operational agents are judged by money and policy outcomes.  
2. **Make ambiguity first-class** — especially timeout-after-commit + idempotency.  
3. **Determinism over realism theater** — seeded world beats flaky live sandboxes for science and CI.  
4. **Soft policy by default** — if tools hard-block everything, you are not testing agent judgment.  
5. **Self-validating benchmark** — Oracle / Naive / mutations must pass before trusting model numbers.  
6. **Model-agnostic harness** — same loop for MockLLM and cloud providers.  
7. **Static, inspectable artifacts** — JSONL traces + HTML site, no opaque SaaS score.

### 3.2 Key decisions (and the alternative rejected)

| Choice | Why | Rejected alternative |
|---|---|---|
| Integer minor units (`Money`) | Exact equality in graders | Floats / decimal strings with rounding debates |
| Derived ledger balances | Single source of truth | Cached balances that can drift from entries |
| Virtual clock + `wait` | Rate-limit / backoff tasks are reproducible | Wall-clock sleeps |
| Named RNG sub-streams | Changing fault RNG doesn’t reshuffle customer ids | One global `random` |
| Soft policy grading | Measures whether agents *choose* compliance | Hard-blocking every P-rule in tools |
| State checkpoints | Falsifiable, mutation-testable | LLM-as-judge on transcripts |
| Scripted customer text | Controlled traps & injections | Free-form multi-agent customer (noise, cost) |
| In-process sim | Fast CI, no infra | Hitting a real sandbox API |
| Static site + optional playground JS | Host anywhere; headline trap is interactive | Full WASM port of the sim (huge scope) |
| Mutation tests on *eligible* core | Kill-rate is meaningful where required sets constrain effects | Claiming 100% on soft lookup-only tasks |

More detail lives in [`DECISIONS.md`](DECISIONS.md).

### 3.3 How the headline trap shaped the architecture

`TIMEOUT_AFTER_COMMIT` forced several structural features:

- Tools must be able to **commit then mask** the response.  
- An **idempotency store** must make “same key” retries safe.  
- Graders must detect **duplicate_transfer** from world state, not from the model’s apology.  
- The playground / compare UX exists specifically so humans can *feel* the trap in seconds.

That single fault type is why PayBench is not “yet another tool-calling accuracy suite.”

---

## 4. Where this design is advantageous

| Advantage | Concrete benefit |
|---|---|
| **Falsifiability** | You can show Oracle 100%, Naive 0% on traps, mutation kill 100% — recruiters and reviewers can verify. |
| **Operational relevance** | Targets real agent failure modes (double pay, skipped verification, injection). |
| **Reproducibility** | Seeds + `state_hash` + replay support scientific comparison across models. |
| **Debuggability** | Full case logs + F1–F15 taxonomy explain *why* a run failed. |
| **Harness hygiene** | Cost guards, resumable runs, provider adapters — mirrors production agent loops. |
| **CI-friendly** | No network required for Oracle/Naive/mutation gates. |
| **Portfolio clarity** | Playground + compare GIF/screenshots communicate the idea without reading the code. |
| **Extensibility** | New tasks = planted world + gold + checkpoints; new models = provider string. |

Compared to “ask GPT to grade the chat”:

- Scores do not depend on a judge model’s mood.  
- Improvements map to **harness/agent behavior**, not prompt cosmetics.  
- Regressions in graders are caught by mutations.

---

## 5. Limitations (honest scope)

- **Simulated rails** — not a certified payments network.  
- **Scripted customer** — no multi-turn negotiation beyond the planted instruction.  
- **Stylized policy** — P1–P9 are representative, not a full compliance library.  
- **Playground ≠ full sim** — browser demo covers the timeout/idempotency story, not all 50 tasks.  
- **Cloud LLM runs** — optional; free tiers can be slow or rate-limited (timeouts, 504s).  
- **Mutation eligibility** — strong kill-rate proof is on tasks with strong required checkpoints, not every soft lookup.

These are deliberate tradeoffs for speed, determinism, and clarity — not accidental omissions.

---

## 6. How we can improve

Ordered by impact vs effort for the current codebase:

### Near-term

1. **Published LLM leaderboard** — multi-model core runs with pass@1 ± CI, safety rate, cost/success on the site.  
2. **Episode trace viewer** — click a failing row → tool log + failed checkpoints + taxonomy.  
3. **OpenAI-compatible base URL** — Ollama / Groq / local models with no new provider surface.  
4. **Richer playground modes** — 2–3 more traps (PII echo, approval-before-refund) as static scenarios.  
5. **Expand mutation eligibility** — more catalog tasks once required sets are strengthened.

### Medium-term

6. **Planner–executor / reflexion baselines** — show technique comparisons, not just model brands.  
7. **pass^k and recovery metrics** surfaced on the leaderboard by default.  
8. **BYO trace grading** — upload JSONL tool traces; grade without re-calling a model.  
9. **Stronger Google/Anthropic adapters** — token accounting, parallel tool-call edge cases, clearer timeouts.  
10. **Packaging** — clean-venv install test, PyPI, GitHub Pages deploy of `site/`.

### Longer-term / research

11. **Partial WASM or server-backed playground** — full sim interactivity in-browser.  
12. **Multi-turn customer** — constrained dialogue tree still seeded for determinism.  
13. **Cross-bench adapters** — export episodes to shared agent-eval formats.  
14. **Differential testing vs a second ledger implementation** — catch sim bugs independent of graders.

---

## 7. Design checklist (when changing the system)

Before merging a change that affects scores:

- [ ] Oracle still 100% on affected tasks (`paybench run --agent oracle` / `paybench validate`)  
- [ ] Naive still fails the relevant traps  
- [ ] New/changed graders have a mutation or unit test that would catch a silent pass  
- [ ] `state_hash` remains stable for unchanged gold traces  
- [ ] Site/compare still rebuilds from real `episodes.jsonl` if UX depends on traces  
- [ ] Document the decision in [`DECISIONS.md`](DECISIONS.md) if it is a lasting tradeoff  

---

## 8. One-paragraph summary

PayBench is designed as a **deterministic, state-graded payments simulator** so that agent evaluation can target **idempotency, ambiguous timeouts, soft policy, and injection** — failure modes that prose graders miss. The architecture separates a pure in-process world from a model-agnostic harness, proves soundness with Oracle/Naive/mutation gates, and exposes results through traces and a static site. That combination is advantageous for reproducible research and portfolio demos; improvements should deepen LLM comparisons and trace UX without abandoning determinism or state-based grading.
