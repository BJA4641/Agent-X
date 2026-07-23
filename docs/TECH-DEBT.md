# AGENT-X — TECHNICAL DEBT REGISTER
**Established:** 2026-07-24 (v5.9.6) · Append-only · Nothing removed without founder approval
Companion to `docs/LEDGER.md`. Debt is tracked separately from features so it cannot be quietly
absorbed into "later".

| ID | Debt | Origin | Interest (cost of carrying) | Payoff plan | Status |
|---|---|---|---|---|---|
| TD-01 | Legacy `pipeline/agent/` coexists with `agentcore`/`workers` and is still imported (`from agent import brain, llm`) | v1.x → v5 migration never completed | Two mental models; audits repeatedly mis-attribute behaviour to dead files; `_has_key` and model routing live in the legacy half | Absorb `llm`/`brain` into `agentcore`, delete the rest | 🟡 REQ-DEADCODE-1, Phase 4 |
| TD-02 | `docs/AGENTS_ROSTER.md` documents a retired 18-agent orchestrator | Never updated after the departments rewrite | Misleads any new reader, including future audits | Rewrite against the 22 live department modules | 🟡 REQ-DEADCODE-1, Phase 4 |
| TD-03 | Self-scheduling chains can multiply across restarts (each restart may add a parallel chain) | Self-scheduling design, v5.x | `human_desk.sync` runs ~every 30s despite a 120s setting — cadence fixes are diluted; becomes N× worse with worker replicas | Single-chain guard keyed on job_type + a claim on the chain | 🟡 REQ-CHAIN-1, Phase 3 |
| TD-04 | ~97% of queue volume is self-maintenance (heartbeat/tick/sync/killswitch) | Accreted across versions | Throughput spent on introspection; masks real work in the feed | Consolidate ops jobs into one supervisor tick | 🟡 REQ-OVERHEAD-2, Phase 3 |
| TD-05 | Single-threaded execution `claim(limit=1)` | Original worker design | Hard throughput ceiling; also the root cause of heartbeat staleness (TD-06 mitigates the symptom) | Thread pool + lanes | 🟡 REQ-PARALLEL-1 / REQ-LANES-1, Phase 2 |
| TD-06 | Liveness now reported by a daemon thread *and* a queued job (two sources of truth) | v5.9.6 REQ-HEALTH-1 fix | Slight redundancy; job-based counts and thread-based timestamp can disagree briefly | Collapse to one source once concurrency lands (Phase 2) | ✅ accepted trade-off, DEC-036 |
| TD-07 | `except Exception: pass` used widely for resilience | Throughout | Genuine failures can hide; caused N-3 and N-7 to go unnoticed for weeks | Convert silent passes on *state-changing* paths to logged warnings (prep skip done in v5.9.6) | 🟡 ongoing, opportunistic |
| TD-08 | No staging environment; production is the test bed | Deployment model (web-UI zip upload) | A bad deploy is discovered by users/DB queries, not by a gate | Post-deploy smoke check asserting version + first job success | 🟡 Phase 1 |
| TD-09 | SLA stage durations are a flat 45-min heuristic, not measured | DEC-022 (accepted: zero data existed) | `at_risk` fires early or late; ETA accuracy is unproven | Replace with rolling p75 once real cycle times exist | 🟡 REQ-LEARN-1, Phase 3 |
| TD-10 | Fairness is page-local (candidate page reorder), not global | DEC-023 | Fine at current volumes; degrades as queue depth grows | Per-account queues + leases | 🟡 REQ-ISOLATION-1, Phase 5 |
| TD-11 | Paused-prep depth cap is 5 outlines with no notion of "complete" | v5.9.5 minimal implementation | Prep stops far short of useful inventory; no decay classification | Redesign per DEC-032 | 🟡 REQ-PREP-REDESIGN, Phase 3 |
| TD-12 | Error strings historically truncated at 150 chars | Pre-v5.9.6 | **Directly caused a multi-session diagnostic failure** — the provider list was cut mid-word, hiding which rungs were attempted | Widened to 900 chars in v5.9.6; audit other truncations | ✅ fixed for the writer, 🟡 audit elsewhere |

## Debt principles adopted (DEC-037)
1. Debt is recorded when it is *created*, including in the release that creates it (see TD-06).
2. Every debt entry names its **interest** — what carrying it costs — not just what it is.
3. A fix that trades one debt for a smaller one is acceptable and must be logged, not hidden.
