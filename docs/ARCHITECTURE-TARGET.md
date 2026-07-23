# AGENT-X — TARGET PRODUCTION ARCHITECTURE
**Date:** 2026-07-24 · **Batch B** · Deliverables 7–11
**Companion documents:** `docs/AUDIT-2026-07-24.md` (Batch A) · `docs/LEDGER.md` (master ledger)
**Design constraint set:** 1 Railway container · 512 MB RAM · Supabase Postgres as system of record ·
$25/account/month hard cap · founder deploys via web UI · no-income-claims policy · paused accounts must cost exactly $0.

---

## 7 · UPDATED PRODUCTION ARCHITECTURE

### 7.1 What is actually wrong with the current architecture

The current design is not badly built — it is **correctly built for the wrong shape of problem.** It was
designed as *one queue serving one factory*. Your business is *N independent factories sharing one supply chain*.

```
TODAY (v5.9.5)                              consequence
┌──────────────────────────────────────┐
│  one shared queue (39,150 jobs)      │
│  fair-ordered, CAS-safe              │  ← fairness fixed starvation
└──────────────┬───────────────────────┘
               │ claim(limit=1)             ← THE bottleneck: strictly sequential
┌──────────────▼───────────────────────┐
│  ONE worker loop, ONE process        │
│  poll 2.5s, 1 job at a time          │  ← 105 accounts share one execution slot
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  model router: paid → free (degrade) │  ← one-way ratchet, no rung back up
│  free A(429) → free B(403) → delay30m│  ← ZERO OUTPUT, ALL TIME
└──────────────────────────────────────┘
```

Three structural defects, in order of business impact:
1. **No upward escalation.** The router degrades gracefully and escalates never. When free capacity hits zero, the factory idles with a full wallet.
2. **Logical parallelism, physical serialization.** `claim(limit=1)` means fairness only decides *whose turn is next*, never *how many run at once*.
3. **Undifferentiated job classes.** A 400-token LLM call and a video render compete for the same single slot with the same memory assumptions.

### 7.2 Target architecture

```
                    ┌───────────────────────────────────────────────┐
                    │  SLA CONTROLLER  (sla.plan_day / sla.monitor)  │
                    │  per-account deadline · backward-planned stages│
                    │  emits: urgency score per account              │
                    └───────────────┬───────────────────────────────┘
                                    │ stamps job.deadline
┌───────────────────────────────────▼───────────────────────────────┐
│  UNIFIED DURABLE QUEUE  (Postgres, CAS claim, idempotency)        │
│  ordering = deadline-urgent block → per-account round-robin       │
│  NEW: job.lane ∈ {light, heavy, free_only}                        │
└───────┬──────────────────────┬──────────────────────┬─────────────┘
        │                      │                      │
┌───────▼────────┐   ┌─────────▼────────┐   ┌─────────▼──────────┐
│ LIGHT LANE     │   │ HEAVY LANE       │   │ FREE-ONLY LANE     │
│ 8 threads      │   │ 1–2 threads      │   │ 2 threads          │
│ LLM/text/DB    │   │ render/visuals   │   │ paused-account prep│
│ IO-bound       │   │ CPU+RAM-bound    │   │ hard $0 guarantee  │
└───────┬────────┘   └─────────┬────────┘   └─────────┬──────────┘
        └──────────────────────┼──────────────────────┘
                    ┌──────────▼───────────────────────────────────┐
                    │  BUDGET-INTELLIGENT MODEL ROUTER              │
                    │  free₁ → free₂ → …free₅ → PAID (SLA-gated)    │
                    │  → cheap-paid → premium-paid → delay (last)   │
                    │  gates: kill switch · daily · $25/acct/month  │
                    │         · CEO decision · deadline pressure    │
                    └──────────────────────────────────────────────┘
```

**Why threads and not processes.** Every light-lane job is dominated by network wait — an HTTPS call to
Gemini/Groq/Anthropic and a Supabase round-trip. Python's GIL releases during IO, so 8 threads in one
512 MB container deliver near-linear throughput on IO-bound work at ~15 MB overhead. Processes would
multiply memory by 8 and blow the container. **This is the single highest-leverage change available
inside your existing infrastructure: ~8× throughput, no new spend, no new services.**

**Why lanes.** Renders are memory-bound and can OOM a 512 MB container if run 8-wide. Splitting lanes
means a heavy render can never starve — or crash — the light LLM work that feeds it.

### 7.3 Migration path (each step independently shippable and reversible)

| Step | Change | Risk | Reversible by |
|---|---|---|---|
| A | Escalation ladder in the router (Batch #2) | Low — gated by existing caps | env flag `ESCALATION_ENABLED=0` |
| B | `claim(limit=N)` + thread pool, light lane only | Medium — concurrency bugs | `WORKER_CONCURRENCY=1` |
| C | Lane classification + per-lane pools | Low | lane defaults to `light` |
| D | 2nd Railway replica | Low — CAS already multi-worker safe | scale replicas to 1 |
| E | Per-account queue partitioning (Phase 7) | High — schema change | not needed until ~50 active accounts |

**Do not do D before B.** A second replica doubles cost and adds heartbeat/chain-multiplication complexity
for 2× throughput; threads give ~8× for free inside the container you already pay for.

---

## 8 · PRODUCTION SLA DESIGN

### 8.1 The contract

> **Every active account completes its full daily production pipeline before 14:00 Asia/Dubai,
> configurable per account.**

Current implementation defaults to an 08:00–22:00 **UTC** window — wrong timezone, wrong deadline (finding N-10).
Corrected model:

```
account.sla_deadline_local = "14:00"          (default, per-account overridable)
account.sla_timezone       = "Asia/Dubai"     (default, per-account overridable)
→ resolved daily to a UTC epoch by sla.plan_day
```

### 8.2 Backward-planned stage deadlines

A single end deadline is not actionable — by the time you breach it, it is too late. The plan therefore
**back-plans each stage** from the publish deadline using measured (initially estimated) stage durations:

| Stage | Default budget | Deadline (for a 14:00 Dubai publish = 10:00 UTC) |
|---|---|---|
| ideate | 5 min | 08:30 UTC |
| write_script | 15 min | 08:45 UTC |
| grade (+1 revision) | 15 min | 09:00 UTC |
| visuals / render | 30 min | 09:30 UTC |
| approve (human or auto) | 20 min | 09:50 UTC |
| publish | 10 min | **10:00 UTC** |

Each spawned job inherits `deadline = stage_deadline`, which the existing `fair_claim_order` already
honours — deadline-urgent jobs jump the queue. **The fairness mechanism shipped in v5.9.5 becomes the
SLA enforcement mechanism the moment stage deadlines are stamped.** No new claiming logic required.

### 8.3 Compliance state machine

| State | Trigger | Automatic response |
|---|---|---|
| `on_track` | all stages ahead of their deadline | none |
| `at_risk` | < 1 stage-budget of runway remains | raise job priority; permit **cheap-paid** escalation |
| `behind` | a stage deadline passed | stamp `deadline=now+600` (queue jump); permit **premium-paid** escalation; allocate extra light-lane threads |
| `breached` | remaining work cannot fit before deadline | escalate to founder desk (`ceo_recommendations`); publish what exists; log a post-mortem row |
| `recovered` | breach → completion same day | record actual stage durations to tune estimates |

### 8.4 Learning loop (replaces the 45-min heuristic)

DEC-022 accepted a flat heuristic because zero cycle-time data existed. Once the first items complete, the
scheduler records **actual stage durations per account** and replaces the constant with a rolling p75.
Honest sequencing: this is worthless until output exists — it is a Phase 3 item, not Batch #2.

### 8.5 SLA metrics (the only four that matter)

1. **Daily SLA hit rate** — % of active accounts publishing full quota before deadline. *Target: ≥ 95%.*
2. **Stage breach distribution** — which stage causes breaches. *Today: 100% at `write_script`.*
3. **Time-to-first-publish per account** — onboarding → first live post.
4. **Cost per published post** — the ROI denominator, per account per day.

---

## 9 · PARALLEL AGENT EXECUTION STRATEGY

### 9.1 Your mandate, restated precisely

> Each account has its own independent pipeline; research, planning, generation, rendering, publishing and
> learning all run in parallel; one slow or failed account never delays another.

**Current status against that mandate: partially met.** v5.9.5 guarantees *non-interference* (no account can
starve another). It does **not** provide *concurrency* (only one job executes at a time). Non-interference
without concurrency means: with 105 active accounts and ~6 jobs each per day at ~40s per job, one worker
needs ~7 hours of continuous perfect execution — with zero retries, zero rate limits, zero renders. The
deadline is unreachable by construction.

### 9.2 Three levels of parallelism, in build order

**Level 1 — In-process concurrency (Batch #3, biggest win per dollar)**
```python
jobs = queue.claim(worker_id, types, limit=CONCURRENCY)   # was limit=1
with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
    pool.map(run_one, jobs)
```
- `WORKER_CONCURRENCY` default 6 for the light lane, 1 for heavy, 2 for free-only.
- Requirements: per-thread Supabase client (the client is not thread-safe), thread-local job context in the
  event bus so feed lines aren't interleaved wrongly, and per-provider rate-limit semaphores.
- Expected: ~6–8× throughput, same container, $0 extra infra.

**Level 2 — Horizontal replicas (after Level 1 proves stable)**
- The CAS claim is already multi-worker safe (proven by design, 39,150 jobs, zero double-claims).
- Blockers to fix first: heartbeat row keyed per `worker_id` (N-3), and self-scheduling chains must be
  claimed by exactly one replica (N-6 chain multiplication becomes N× worse with N replicas).
- Expected: linear in replica count, linear in cost. Use only when Level 1 saturates.

**Level 3 — Per-account isolation (Phase 7, at ~50+ active accounts)**
- `jobs.lane_key = account_id`, a lease table granting each account a bounded slice of workers,
  and per-account circuit breakers so a poisoned account trips only its own lane.
- **Honest recommendation: do not build this yet.** Level 1 + deadline-aware fairness delivers your
  business requirement (independent daily production per account) at 105 accounts. Level 3 is the
  answer at ~500. Building it now is expensive insurance against a problem you do not have.

### 9.3 What "parallel" must never mean

- **Never parallel spend.** Concurrency multiplies burn rate. Every escalation still passes the CEO gate,
  daily budget, and $25/account cap — checked *inside* each thread, not once per batch.
- **Never parallel publishing to one account.** Two posts landing simultaneously on one Instagram handle
  is a platform-risk pattern. Publishing stays serialized *per account*, parallel *across accounts*.
- **Never parallel free-tier hammering.** 8 threads × Gemini = instant 429 (this is already happening at
  concurrency 1). Per-provider semaphores + shared token bucket are **mandatory** before Level 1 ships.

---

## 10 · BUDGET STRATEGY

### 10.1 The core inversion

The current system optimizes **cost minimization**. It succeeded: spend fell from $6.70 to $1.15/day.
It also produced nothing. Cost per published post is undefined because the denominator is zero — the
cheapest possible outcome is also the worthless one.

> **New objective: maximize published posts per dollar, subject to hard caps — not minimize dollars.**

### 10.2 The escalation ladder (the fix for N-1)

```
1. free tier      gemini-2.5-flash          $0        ← try always
2. free tier      groq llama-3.3-70b        $0        ← currently 403, founder fix
3. free routes    openrouter ×3 (gemma/nemotron/gpt-oss)  $0  ← currently unreachable, NO KEY
   ─────────────── if all free exhausted ───────────────
4. cheap paid     haiku-class / flash-paid  ~$0.002   ← gate: at_risk OR free_exhausted
5. premium paid   sonnet-class              ~$0.02    ← gate: behind/breached OR quality-critical
6. delay 30 min   (LAST RESORT ONLY)                  ← today this is rung 3, and it is why output is zero
```

**Escalation decision function** — all conditions must hold:
```
escalate_to_paid  IFF
      free_exhausted(provider_states)          # 429/403 across all free routes
  AND kill_switch == off
  AND cost_mode != free_only
  AND daily_budget_remaining  > est_cost
  AND account_month_spend + est_cost <= $25
  AND ceo_decide(...) != deny
  AND ( sla_state in {at_risk, behind, breached}   # deadline pressure
        OR account_produced_today == 0 )           # nothing shipped yet today
```
The last clause is deliberate: **an account that has published nothing today always justifies one paid
attempt**, because the marginal value of a first post far exceeds $0.02.

### 10.3 Spend envelope at scale (arithmetic that must hold)

| Scenario | Accounts | Posts/day | Free coverage | Paid cost/day | Monthly |
|---|---|---|---|---|---|
| Today (broken) | 2 active | 0 | 0% (429/403) | $1.15 (wasted on ideation) | ~$35 |
| Batch #2 fixed | 2 active | 2 | ~60% | ~$0.05 | ~$1.50 |
| 10 accounts | 10 | 10 | ~50% | ~$0.30 | ~$9 |
| 105 accounts | 105 | 105 | ~30% (free tier saturates) | ~$4.50 | ~$135 |

At 105 accounts the $25/account cap ($2,625/month theoretical) is never approached — the real constraint
is free-tier saturation, not the cap. **The cap is not your binding constraint; free-tier rate limits are.**

### 10.4 Budget intelligence rules

| Question | Rule |
|---|---|
| When are free models sufficient? | Always try first. Free output that passes grade ≥ 7.0 ships unchanged. |
| When is premium justified? | SLA `behind`/`breached`, or an account with proven revenue, or a first-of-day post. |
| When to upgrade quality? | When grader rejects a free draft twice — a third free attempt has low marginal value. |
| When to defer expensive work? | Renders/visuals when the script has not passed grading. Never defer the writer. |
| When to pause production? | Kill switch, cap exhausted, or **no-output-with-spend** guard (already built and correct). |
| When to prioritize a brand? | Rank by realized revenue per dollar, then SLA breach risk. |
| When to add workers? | When queue depth × avg job time > remaining SLA runway. This is the *only* legitimate trigger. |

### 10.5 Immediate founder actions (no code required)

1. **Replace the Groq key** — currently HTTP 403. Restores free rung 2.
2. **Add an `OPENROUTER_API_KEY`** — unlocks free rungs 3–5 (three Apache-2.0 models, currently unreachable). This is the single cheapest capacity increase available: $0 for 3× more free writing attempts.

---

## 11 · PAUSED ACCOUNT STRATEGY — CRITICAL REVIEW & REDESIGN

### 11.1 Your proposal

Paused accounts should continuously work on free models: improve Brand Bible, improve Business Plan,
research competitors, monitor trends, build content calendars, draft scripts, generate captions, build
hashtag libraries, improve SEO, prepare publishing schedules, improve prompts, optimize workflows,
generate future content ideas, build platform-specific strategies — so that on resume, weeks of optimized
content already exist.

### 11.2 Critical review — the strategic intent is right, the resource model is wrong

**What is right:** the insight is genuinely strong. Preparation is the one activity whose cost can be
near-zero while its value is realized later at full price. 103 idle accounts compounding prepared inventory
is real, defensible leverage, and it converts your biggest liability (idle inventory) into an asset.

**What is wrong — and this audit proved it empirically:**

> **Free capacity is not free. It is a scarce shared resource, and it is currently at zero.**

Live evidence: `paused.prep_cycle` ran twice and banked **0 items** — Gemini returned 429, Groq 403.
Simultaneously, the *active* accounts' writer was blocked by the **same** two failures. Paused prep and
live production are competing for one exhausted pool.

Four specific flaws in the proposal as stated:

1. **Resource contention with revenue work.** "Continuously" × 103 accounts × 14 activities would consume
   every free token available — starving the two accounts that could actually publish today. Prep work must
   be strictly *subordinate* to live production, never merely concurrent with it.
2. **Unbounded work with no completion state.** "Continuously improve the Brand Bible" has no definition of
   done. A brand bible improved 400 times is not 400× better; after ~3 passes the marginal gain is noise.
3. **Perishable vs durable outputs are conflated.** A hashtag library is durable for months. A trend
   observation is stale in 72 hours. Preparing trend-dependent content weeks ahead **destroys** value —
   you resume an account and publish stale takes.
4. **No quality gate.** Free-model output banked unread for weeks means resuming an account floods the
   board with ungraded drafts. Volume of prepared content is not the metric; *usable* prepared content is.

### 11.3 Redesigned paused-account architecture

**Principle: Prep is a scavenger, not a citizen.** It consumes only capacity that live production
provably does not need, produces bounded durable artifacts, and is graded before it is banked.

**(a) Strict subordination — the free-capacity budget**
```
free_tokens_available_this_hour
  ─ reserved for ACTIVE accounts (100% of need, always first)
  = surplus
prep may consume ≤ surplus, and only when NO active account is at_risk/behind/breached
```
Implemented as a check at the top of `prep_cycle`: if any active account is behind SLA, **prep skips
entirely this cycle.** This one rule resolves the contention flaw and costs nothing to build.

**(b) Classify the 14 activities by decay rate — this is the core redesign**

| Tier | Activities | Cadence | Depth cap | Rationale |
|---|---|---|---|---|
| **DURABLE** (build once, refine rarely) | Brand Bible, Business Plan, platform strategies, hashtag libraries, SEO keyword sets, prompt packs | Build once → refine max **3×** → frozen | 1 artifact each | Marginal value collapses after ~3 passes |
| **SLOW-DECAY** (refresh monthly) | Competitor research, workflow optimization, content calendar skeleton | Monthly refresh | 1 per month | Competitive landscape moves in months |
| **PERISHABLE** (do NOT prepare far ahead) | Trend monitoring, trend-jacking ideas, timely scripts | Observe & store signals only; **do not draft** | rolling 7-day window | Drafting on stale trends destroys value |
| **EVERGREEN INVENTORY** (the real prize) | Evergreen scripts + captions on timeless niche topics | Until cap reached | **20 per account** | This is what actually converts on resume |

**(c) Depth caps replace "continuous"**
An account is `prep_complete` when it holds: 1 brand bible, 1 business plan, 1 platform strategy set,
1 hashtag library, 1 SEO set, 1 calendar skeleton, and 20 graded evergreen scripts. It then **stops
consuming resources entirely** and re-enters rotation only for monthly slow-decay refresh. Current
implementation caps at 5 outlines with no notion of completeness — too shallow and never finished.

**(d) Grade before banking**
Every prepped script passes the existing free grader. Below 6.0 → discarded, not banked. On resume you
inherit *usable* inventory, not raw volume.

**(e) Rotation by expected value, not round-robin**
Priority = `(niche_evergreen_potential × account_readiness) / prep_completeness`. Accounts closest to
being resumed, in the most durable niches, get prepared first.

**(f) Resume bridge (REQ-PREP-PROMOTE)**
On unpause: promote the highest-graded prep scripts to `idea` status, re-validate trend-sensitivity,
and refresh anything older than 30 days. The account starts producing within one tick instead of
starting from ideation.

### 11.4 Honest expected value

With the redesign, 103 paused accounts converge to ~20 graded evergreen scripts each ≈ **2,060 ready-to-produce
items** — roughly 20 days of content per account at 1 post/day, at $0 model cost. That is the outcome you
described, achieved with bounded resources instead of unbounded ones.

**But the sequencing must be honest: none of this works until free capacity exists.** With Gemini at 429
and Groq at 403, the prep engine runs and banks nothing — exactly what is happening now. **Fix the keys and
the escalation ladder first; the paused-account program is worthless before then and compounds afterward.**

---

## SUMMARY OF ARCHITECTURAL DECISIONS PROPOSED IN BATCH B

| ID | Decision | Status |
|---|---|---|
| DEC-028 | Escalation ladder added above the free tier; delay demoted to last resort | 🔵 proposed — Batch #2 |
| DEC-029 | Concurrency via **threads** (IO-bound work), not processes or replicas, as the first parallelism step | 🔵 proposed — Batch #3 |
| DEC-030 | Job **lanes** (light / heavy / free-only) with per-lane pool sizes to protect the 512 MB container | 🔵 proposed — Batch #3 |
| DEC-031 | SLA is **back-planned per stage**; stage deadlines feed the existing fairness ordering | 🔵 proposed — Batch #2 |
| DEC-032 | Paused prep is **subordinate, bounded, decay-classified and graded** — not continuous | 🔵 proposed — supersedes current prep_cycle |
| DEC-033 | Per-account queue isolation deferred to ~50 active accounts; Level 1+2 sufficient below that | 🔵 proposed |

*Batch C follows: Master Roadmap, WSJF-scored Prioritized Action Plan, Risks & Recommendations, Executive Summary.*
