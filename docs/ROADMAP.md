# AGENT-X — MASTER ROADMAP, RISKS & EXECUTIVE SUMMARY
**Date:** 2026-07-24 · **Batch C** · Deliverables 5, 12, 13
**Companions:** `docs/AUDIT-2026-07-24.md` (A) · `docs/ARCHITECTURE-TARGET.md` (B) · `docs/ACTION-PLAN.md` (WSJF) · `docs/LEDGER.md`

---

## 0 · LATE-BREAKING FINDING (supersedes part of Batch A/B)

While preparing this roadmap I traced *why* the three OpenRouter free routes never fire. The result changes
the priority order, so it is recorded before the roadmap.

**The free ladder is not the 5-rung constant in the code.** `council._order()` reads
`settings.free_council_models` and — if that row exists — **replaces `_FREE_ORDER` entirely** rather than
merging with it. That row is written autonomously by `strategy.arena_scout`.

Live value of `settings.free_council_models` (updated 21:28 UTC by arena scout):
```
1. gemini      gemini-2.5-flash              "free tier"        ← 429 rate-limited
2. groq        llama-3.3-70b-versatile       "free tier"        ← was 403, key now replaced
3. openrouter  google/gemma-4-31b-it:free    "arena #52"
4. openrouter  cohere/north-mini-code:free   "free route"
5. openrouter  google/gemma-4-26b-a4b-it:free "free route"
```

Two conclusions, both important:

1. **The recorded failures predate this row.** The last council failure (`gemini 429 | groq 403`) is stamped
   ~38 minutes *before* this ladder was written. At that moment the ladder held only 2 rungs. The next
   30-minute retry of the queued `write_script` jobs is the live test of whether rungs 3–5 now fire.
   **Your Groq key replacement + this expanded ladder may unblock production without any code change.**
   Verification query is in §5.
2. **The structural defect remains regardless.** A self-improving component (`arena_scout`) can silently
   *narrow* the safety ladder, and there is no floor. That is how a 5-rung fallback became a 2-rung fallback
   with nobody noticing, and it is the mechanism behind the all-time zero-output record. `_order()` must
   **merge** (arena picks first, `_FREE_ORDER` appended, deduped) so the hardcoded floor can never be
   removed by an autonomous agent. This is a ~5-line fix and it is now the single highest-value item on the
   roadmap — higher than paid escalation, because it costs $0 and hardens against recurrence.

**Revised #1 priority:** ladder floor merge (REQ-LADDER-FLOOR) → then paid escalation (REQ-ESCALATE-1).

---

## 5 · MASTER ROADMAP

Rebuilt from the current audit, not continued from prior versions. Every phase states objective, priority,
rationale, tasks, dependencies, deliverables, success metrics, effort and risk-if-skipped.

### PHASE 0 — "FIRST POST" · Unblock output
**Objective:** one real published post for one account. **Priority:** CRITICAL — nothing else matters until this exists.
**Why it matters:** the platform has produced 0 published items in its entire history. Every other metric,
grade, feature and strategy in this document is speculative until the loop closes once.

| Tasks | REQ |
|---|---|
| Merge (not replace) the free ladder — guarantee a hardcoded floor | REQ-LADDER-FLOOR |
| SLA-aware paid escalation rung above free-exhausted | REQ-ESCALATE-1 |
| Age out stalled items from the demand-governor in-flight count | REQ-GOV-2 |
| Idempotency key on re-plan → write_script spawn | REQ-DEDUPE-1 |
| Heartbeat write repair + surface silent skips | REQ-HEALTH-1, REQ-PREPOBS-1 |
| SLA deadline default → 14:00 Asia/Dubai, per-account overridable | REQ-SLA-TZ |
| End-to-end integration test: ideate → approved against stub provider | REQ-E2E-1 |

**Dependencies:** none (Groq key ✅ replaced by founder, OpenRouter key ✅ confirmed present).
**Deliverables:** v5.9.6 zip, migration notes, changelog, updated tests.
**Success metrics:** ≥1 item reaches `published`; `write_script` success rate > 80%; cost/post < $0.05.
**Effort:** 1 batch. **Risk if skipped:** the company remains a $0-revenue engineering exercise indefinitely.

### PHASE 1 — "PROVE THE LOOP" · Repeatable daily output for 2 accounts
**Objective:** both live accounts hit quota before deadline, 7 consecutive days. **Priority:** CRITICAL.
**Why:** proves the SLA design works before it is scaled to 105 accounts.

Tasks: auto-approve rule above a grade threshold (removes the human bottleneck); publishing OAuth for one
platform end-to-end; stage-deadline stamping (REQ-SLASTAGE-1); first cost-per-post measurement.
**Dependencies:** Phase 0. **Deliverables:** publish pipeline live on 1 platform; SLA hit-rate dashboard.
**Metrics:** 7-day SLA hit rate ≥ 90%; time-to-publish < 4h; zero manual interventions.
**Effort:** 1–2 batches. **Risk if skipped:** scaling an unproven loop multiplies failure, not output.

### PHASE 2 — "THROUGHPUT" · Physical parallelism
**Objective:** 8× execution capacity inside the existing container. **Priority:** HIGH.
**Why:** at `claim(limit=1)`, 105 accounts require ~7h of flawless sequential execution — the SLA is
unreachable by construction.

Tasks: per-provider rate-limit semaphores (REQ-RATELIMIT-1 — **must land before concurrency**);
`claim(limit=N)` + thread pool (REQ-PARALLEL-1); job lanes light/heavy/free-only (REQ-LANES-1);
thread-safe Supabase clients and event-bus context.
**Dependencies:** Phase 1 (do not parallelize a broken loop). **Metrics:** ≥6 concurrent jobs; no OOM at
512MB; 429 rate unchanged or lower. **Effort:** 1–2 batches. **Risk if skipped:** hard ceiling at ~10 accounts.

### PHASE 3 — "SCALE & LEARN"
**Objective:** 20+ active accounts meeting SLA; system tunes itself from real data. **Priority:** HIGH.
Tasks: 2nd Railway replica (REQ-SCALE-WORKERS) after chain-multiplication fix (REQ-CHAIN-1); replace the
45-min heuristic with measured p75 stage durations; overhead reduction (REQ-OVERHEAD-2 — 97% of jobs are
self-maintenance); paused-prep redesign (REQ-PREP-REDESIGN) + resume bridge (REQ-PREP-PROMOTE).
**Metrics:** 20 accounts at ≥95% SLA; self-maintenance < 50% of jobs; ≥20 graded prep items/paused account.
**Effort:** 2–3 batches. **Risk if skipped:** paused inventory stays worthless; costs scale linearly with accounts.

### PHASE 4 — "MONETIZE & HARDEN"
**Objective:** first revenue attributed to a published post. **Priority:** MEDIUM.
Tasks: Stripe Connect payout automation (REQ-PAYOUT-1); revenue-per-account attribution feeding budget
priority; SLA UI (REQ-SLA-UI); per-account monthly-cap surfacing (REQ-BUDGET-2); dead-code removal
(REQ-DEADCODE-1); admin audit log; secret rotation policy.
**Metrics:** ≥1 attributed conversion; budget priority ranked by realized revenue.
**Effort:** 2 batches. **Risk if skipped:** the platform optimizes cost forever with no revenue signal.

### PHASE 5 — "HUNDREDS OF BRANDS"
**Objective:** the stated end-state. **Priority:** FUTURE — do not start before Phase 3 completes.
Tasks: per-account queue partitioning + leases (REQ-ISOLATION-1); per-account circuit breakers; multi-region
render capacity; automated brand onboarding; learned model-selection per niche.
**Metrics:** 100+ accounts, ≥95% SLA, cost/post flat or falling as volume rises.
**Risk if skipped:** none near-term — this is insurance against a problem you do not yet have.

---

## 12 · RISKS & RECOMMENDATIONS

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | **Autonomous config narrows safety defaults** (arena_scout replaced a 5-rung ladder with 2) | **Occurred** | **Critical** | Merge-not-replace with a hardcoded floor; alert when the ladder shrinks below 3 rungs |
| R-2 | Free tiers saturate as accounts scale — 429s become the norm | High | Critical | Paid escalation + per-provider token buckets + staggered scheduling |
| R-3 | Concurrency multiplies spend faster than output | Medium | High | Budget checks inside each thread, never once per batch; per-account cap enforced pre-call |
| R-4 | Observability lies (heartbeat staleness) hide real failures | Occurred | High | Fix write path; alert on `now − last_heartbeat > 3×interval`; post-deploy smoke check |
| R-5 | Key-person dependency — one founder holds all deploys, keys, approvals | High | Critical | Document runbook; auto-approve rules reduce human-in-loop; consider a trusted second operator |
| R-6 | Platform policy risk (IG/TikTok inauthentic-content enforcement) | Medium | High | Original scripts only (already policy); AI disclosure; conservative per-account posting cadence |
| R-7 | Trademark collision with agentx.so blocks go-to-market | Medium | High | **Decide before any paid marketing** — REQ-TRADEMARK 🔵 |
| R-8 | Publishing OAuth incomplete — approved content cannot post | High | Critical | Phase 1; one platform end-to-end before breadth |
| R-9 | Prep inventory ages into staleness before resume | Medium | Medium | Decay classification + 30-day refresh on promote (DEC-032) |
| R-10 | No staging environment; production is the test bed | High | Medium | Post-deploy smoke check asserting version + first job success |

**Top recommendations, in order**
1. **Ship the ladder floor merge first.** $0 cost, fixes the mechanism that caused total output failure, and prevents recurrence by any future autonomous agent.
2. **Do not scale before one post publishes.** Every throughput improvement multiplies a loop that currently produces zero.
3. **Measure cost-per-published-post from day one.** It is the only metric that makes the budget system's success legible; today its denominator is zero.
4. **Resolve the trademark before marketing spend.** It is cheap now and expensive after brand equity accrues.
5. **Treat autonomous self-modification as a risk class.** Arena scout narrowing the ladder is the first instance; any agent that writes config another agent depends on needs a floor and an alert.

---

## 13 · EXECUTIVE SUMMARY

**Where the project stands.** Agent-X is a well-engineered platform that has never delivered its product.
The infrastructure grades **7.5/10** — durable Postgres job queue with 99.93% success across 39,150 jobs,
event sourcing, layered cost governance, RLS on 100% of tables, a CI gate, and a test suite built from real
production incidents. The content pipeline grades **3.0/10** — 7,408 board items cleared, **zero published,
all time**. Overall: **5.9/10 — an excellent engine with no output.**

**Why.** Not architecture, not agents, not budget. The writer's fallback ladder ended at *"delay 30 minutes"*
with no rung that escalates to a paid model — while $23.85 of a $25 monthly cap sat unused. Worse, the
autonomous `arena_scout` agent had silently **replaced** the 5-rung free ladder with a 2-rung one; when
Gemini rate-limited and the Groq key expired, free capacity hit exactly zero and the factory idled with a
full wallet. One missing rung and one missing floor, sitting directly on the critical path, dragging a
7.5-quality system to a 3.0 business result.

**What genuinely improved.** Nine prior findings verified closed this audit: RLS exposure 9 tables → 0;
ideation churn ~517/day → 13/day; spend $6.70 → $1.15/day; the empty-topic fatal class eliminated; CI gate
live; canonical schema restored; v5.9.5 deployed with SLA planning and monitoring confirmed populating real
per-account state. The engineering discipline is working — the ledger, decision log and incident-derived
tests are above the standard of most funded startups.

**What it will take.** Phase 0 is one batch of work and produces the first published post. Phase 1 proves the
loop repeats for two accounts. Phase 2 delivers ~8× throughput via threads inside the container you already
pay for — no new infrastructure. Only then does scaling to 105 accounts become an engineering problem rather
than a gamble. At full scale the economics hold comfortably: ~$135/month against a $2,625 theoretical cap —
your binding constraint was never money, it was free-tier rate limits.

**The one-line version.** *The company is one fallback rung away from having a product, and the fix costs
nothing. Everything after that is throughput.*

**Immediate next step:** approve Batch #2 (Phase 0). Verification query for whether your key updates already
unblocked production is in §5 of `docs/ACTION-PLAN.md`.
