# AGENT-X — PRIORITIZED ACTION PLAN (WSJF-SCORED)
**Date:** 2026-07-24 · **Batch C** · Deliverable 6
**Companion:** `docs/ROADMAP.md` · `docs/AUDIT-2026-07-24.md` · `docs/ARCHITECTURE-TARGET.md`

---

## 1 · SCORING METHOD

**WSJF (Weighted Shortest Job First), SAFe formulation:**

```
                Business Value + Time Criticality + Risk Reduction / Opportunity Enablement
WSJF  =  ──────────────────────────────────────────────────────────────────────────────────
                                        Job Size
```

All inputs use a modified Fibonacci scale (1, 2, 3, 5, 8, 13). Higher WSJF = do sooner.

- **BV — Business Value:** direct contribution to published posts, revenue, or cost per post.
- **TC — Time Criticality:** how fast the value decays, or how much else is blocked behind it.
- **RR/OE — Risk Reduction / Opportunity Enablement:** failure modes removed or future work unlocked.
- **JS — Job Size:** engineering effort *including* test and verification burden.

Supporting columns per your prompt: Business Impact, Engineering Impact, Complexity, ROI.

---

## 2 · MASTER WSJF TABLE (all open items, ranked)

| Rank | ID | Task | BV | TC | RR/OE | CoD | JS | **WSJF** | Phase |
|---|---|---|---|---|---|---|---|---|---|
| 1 | REQ-LADDER-FLOOR | Merge (not replace) free ladder; hardcoded floor + shrink alert | 13 | 13 | 13 | 39 | 1 | **39.0** | 0 |
| 2 | REQ-KEYS-2 ✅ | Replace Groq key (founder — **done**) | 13 | 13 | 8 | 34 | 1 | **34.0** | 0 |
| 3 | REQ-ESCALATE-1 | SLA-aware paid escalation rung above free-exhausted | 13 | 13 | 8 | 34 | 3 | **11.3** | 0 |
| 4 | REQ-GOV-2 | Age out stalled items from in-flight demand count | 8 | 8 | 5 | 21 | 2 | **10.5** | 0 |
| 5 | REQ-DEDUPE-1 | Idempotency key on re-plan → write_script | 5 | 8 | 8 | 21 | 2 | **10.5** | 0 |
| 6 | REQ-HEALTH-1 | Heartbeat write repair + staleness alert | 5 | 8 | 8 | 21 | 2 | **10.5** | 0 |
| 7 | REQ-SLA-TZ | SLA deadline → 14:00 Asia/Dubai, per-account | 8 | 5 | 3 | 16 | 2 | **8.0** | 0 |
| 8 | REQ-PREPOBS-1 | Surface silent prep/provider skips | 3 | 5 | 8 | 16 | 2 | **8.0** | 0 |
| 9 | REQ-AUTOAPPROVE-1 | Auto-approve above grade threshold (removes human bottleneck) | 13 | 8 | 3 | 24 | 3 | **8.0** | 1 |
| 10 | REQ-E2E-1 | End-to-end integration test vs stub provider | 5 | 5 | 13 | 23 | 3 | **7.7** | 0 |
| 11 | REQ-RATELIMIT-1 | Per-provider semaphores + token bucket | 8 | 8 | 13 | 29 | 5 | **5.8** | 2 |
| 12 | REQ-SLASTAGE-1 | Back-planned per-stage deadlines | 8 | 5 | 5 | 18 | 3 | **6.0** | 1 |
| 13 | REQ-PARALLEL-1 | claim(limit=N) + thread pool (~8× throughput) | 13 | 8 | 8 | 29 | 5 | **5.8** | 2 |
| 14 | REQ-PUB-TOKENS 🔴 | Publishing OAuth, one platform end-to-end | 13 | 13 | 5 | 31 | 8 | **3.9** | 1 |
| 15 | REQ-LANES-1 | Job lanes + per-lane pools (OOM protection) | 5 | 5 | 8 | 18 | 3 | **6.0** | 2 |
| 16 | REQ-CHAIN-1 | Stop self-scheduling chain multiplication | 3 | 5 | 8 | 16 | 3 | **5.3** | 3 |
| 17 | REQ-OVERHEAD-2 | Cut self-maintenance share (97% of jobs) | 5 | 3 | 5 | 13 | 3 | **4.3** | 3 |
| 18 | REQ-PREP-PROMOTE | Resume bridge: prep → live funnel | 8 | 3 | 3 | 14 | 3 | **4.7** | 3 |
| 19 | REQ-SCALE-WORKERS | 2nd Railway replica | 8 | 5 | 3 | 16 | 5 | **3.2** | 3 |
| 20 | REQ-PREP-REDESIGN | Paused prep: subordinate, capped, decay-classified, graded | 8 | 3 | 5 | 16 | 5 | **3.2** | 3 |
| 21 | REQ-BUDGET-2 | Per-account cap + spend bar in UI | 3 | 3 | 3 | 9 | 3 | **3.0** | 4 |
| 22 | REQ-SLA-UI | SLA chips + prep filter in Studio | 3 | 3 | 3 | 9 | 3 | **3.0** | 4 |
| 23 | REQ-LEARN-1 | Replace 45-min heuristic with measured p75 | 5 | 2 | 5 | 12 | 5 | **2.4** | 3 |
| 24 | REQ-TRADEMARK 🔵 | Resolve Agent-X vs agentx.so | 8 | 5 | 8 | 21 | 8 | **2.6** | — |
| 25 | REQ-PAYOUT-1 | Stripe Connect payout automation | 5 | 2 | 3 | 10 | 5 | **2.0** | 4 |
| 26 | REQ-DEADCODE-1 | Remove legacy pipeline/agent/, refresh roster docs | 2 | 2 | 5 | 9 | 5 | **1.8** | 4 |
| 27 | REQ-MCP-CLAIMS 🔵 | Scope MCP claims honestly pre-marketing | 3 | 2 | 5 | 10 | 3 | **3.3** | 4 |
| 28 | REQ-ISOLATION-1 | Per-account queues + leases | 8 | 1 | 8 | 17 | 13 | **1.3** | 5 |

**Note on rank 14:** REQ-PUB-TOKENS has the second-highest Cost of Delay in the entire plan (31) but a large
job size, so WSJF ranks it below quick wins. This is WSJF working correctly — do the 1-point items first,
they unblock in hours. But it must not slip past Phase 1: **approved content that cannot post is still zero output.**

---

## 2B · PHASE-5 ITEMS — NOW SCORED (closes gap G-4)

| ID | Task | BV | TC | RR/OE | CoD | JS | **WSJF** |
|---|---|---|---|---|---|---|---|
| REQ-CIRCUIT-ACCT | Per-account circuit breakers (a poisoned account trips only its own lane) | 5 | 1 | 8 | 14 | 8 | **1.8** |
| REQ-RENDER-REGION | Multi-region render capacity | 3 | 1 | 3 | 7 | 8 | **0.9** |
| REQ-ONBOARD-AUTO | Automated brand onboarding (self-serve new account → producing) | 8 | 2 | 5 | 15 | 8 | **1.9** |
| REQ-MODEL-NICHE | Learned per-niche model selection | 5 | 1 | 5 | 11 | 8 | **1.4** |

All four rank below every Phase 0–3 item, confirming the roadmap sequencing: they are insurance against
scale problems that do not exist at 2 active accounts.

## 2C · FULL IMPACT SCORING FOR EVERY TIER (closes gap G-3)

| ID | Business Impact | Engineering Impact | Complexity | ROI |
|---|---|---|---|---|
| REQ-AUTOAPPROVE-1 | High — removes the founder from every publish path (the Phase-1 throughput ceiling) | Approval-policy gate; fails closed on error | Low | Very High |
| REQ-SLASTAGE-1 | High — converts v5.9.5 fairness into real SLA enforcement | One central stamping site, no spawn-site changes | Low | Very High |
| REQ-COSTPOST-1 | High — supplies the ROI denominator cost control never had | Read-only aggregation | Trivial | Very High |
| REQ-PUB-TOKENS | Extreme — approved content still cannot post | Token storage + refresh + per-platform quirks | High | High (blocked on founder) |
| REQ-RATELIMIT-1 | High — prevents 429 storms that worsen under threads | Semaphores + shared token bucket | Medium | High |
| REQ-PARALLEL-1 | Extreme at scale — SLA unreachable single-threaded | Thread-safe clients, bus context, per-lane pools | Medium-High | Very High |
| REQ-LANES-1 | Medium — OOM protection at 512MB | Lane classification on spawn | Low | High |
| REQ-CHAIN-1 | Medium — cadence fixes currently diluted ~4× | Single-chain guard | Low | Medium |
| REQ-OVERHEAD-2 | Medium — reclaims 97% of queue capacity | Ops job consolidation | Medium | Medium |
| REQ-SCALE-WORKERS | High at scale | Config + heartbeat dedupe | Low | Medium (costs money) |
| REQ-PREP-REDESIGN | High — 103 idle accounts compound inventory | Prep governor + decay classification + grading | Medium | High |
| REQ-PREP-PROMOTE | Medium — instant production on unpause | Promotion + staleness refresh | Low | Medium |
| REQ-LEARN-1 | Medium — ETA accuracy | Rolling percentile store | Medium | Low until output exists |
| REQ-BUDGET-2 | Medium — founder visibility of the $25 cap | Web layer only | Low | Medium |
| REQ-SLA-UI | Medium — makes SLA state legible | Web layer only | Low | Medium |
| REQ-WEB-404 | **High — three sidebar links 404 today; founder-visible breakage** | 3 Next.js pages + data wiring | Low-Medium | High |
| REQ-PAYOUT-1 | Medium — affiliate payouts are manual | Connect onboarding + webhooks | Medium | Medium |
| REQ-DEADCODE-1 | Low direct, high clarity | Removes a shadow codebase | Medium | Medium |
| REQ-ISOLATION-1 | High at 500 brands | Schema change, migration risk | High | Low now, High later |
| REQ-TRADEMARK | High — blocks marketing spend | None (legal) | Medium | High |
| REQ-MCP-CLAIMS | Medium — honesty policy | None | Low | Medium |

## 3 · CATEGORIZED WORK

### 🔴 CRITICAL — immediately (Batch #2 / v5.9.6)
| Task | Business Impact | Engineering Impact | Complexity | ROI |
|---|---|---|---|---|
| REQ-LADDER-FLOOR | Restores 3 dead free rungs at $0 | Removes a whole failure class (autonomous config narrowing) | Trivial (~5 lines) | **Extreme** |
| REQ-ESCALATE-1 | Converts a full wallet into published posts | Adds the missing upward rung to the router | Low-Medium | **Extreme** |
| REQ-GOV-2 | Unfreezes ideation when downstream stalls | Governor becomes stall-tolerant | Low | Very High |
| REQ-DEDUPE-1 | Prevents 5× spend multiplication once paid escalation lands | Consistency with existing idempotency discipline | Low | Very High |
| REQ-HEALTH-1 + REQ-PREPOBS-1 | Restores trust in every health signal | Kills two silent-failure paths | Low | High |
| REQ-SLA-TZ | SLA finally measures the deadline you actually mandated | Config + resolution logic | Low | High |
| REQ-E2E-1 | Would have caught the zero-output defect on day one | Proves the whole loop, not just the parts | Medium | High |

### 🟠 HIGH — blocks production or scale (Phase 1–2)
REQ-AUTOAPPROVE-1 · REQ-PUB-TOKENS 🔴 · REQ-SLASTAGE-1 · REQ-RATELIMIT-1 · REQ-PARALLEL-1 · REQ-LANES-1

### 🟡 MEDIUM — quality and efficiency (Phase 3–4)
REQ-CHAIN-1 · REQ-OVERHEAD-2 · REQ-PREP-PROMOTE · REQ-PREP-REDESIGN · REQ-SCALE-WORKERS · REQ-BUDGET-2 ·
REQ-SLA-UI · REQ-LEARN-1 · REQ-PAYOUT-1 · REQ-DEADCODE-1

### 🔵 FUTURE — after production stability (Phase 5)
REQ-ISOLATION-1 · per-account circuit breakers · multi-region render · automated brand onboarding ·
learned per-niche model selection

### 🔵 FOUNDER DECISIONS (not engineering)
REQ-TRADEMARK (blocks marketing spend) · REQ-MCP-CLAIMS (blocks honest advertising)

---

## 4 · RECOMMENDED BATCH #2 CONTENT (awaiting your approval)

Ranks 1, 3, 4, 5, 6, 7, 8, 10 — every CRITICAL item. Combined job size ≈ 17 points, combined Cost of Delay
≈ 172. This is the highest-density value batch available and it is the batch that produces your first
published post.

Explicitly **not** in Batch #2: concurrency, replicas, paused-prep redesign, UI work. Rationale: none of
them produce a published post while the ladder is broken, and parallelizing a zero-output loop multiplies zero.

---

## 5 · VERIFICATION QUERY — did your key updates already unblock production?

The Groq key you replaced and the OpenRouter routes added by arena scout at 21:28 UTC postdate the last
recorded council failure. The queued `write_script` jobs retry every 30 minutes. Run this after the next
retry window to see whether the pipeline moved on its own:

```sql
SELECT
  (SELECT count(*) FROM board_items WHERE status IN ('drafted','approved','scheduled','published'))
    AS items_past_idea,
  (SELECT count(*) FROM jobs
     WHERE job_type='creative.write_script' AND status='done'
       AND created_at > extract(epoch from now()) - 3600)              AS scripts_written_last_hour,
  (SELECT substring(coalesce(error,'none'),1,120) FROM jobs
     WHERE job_type='creative.write_script' ORDER BY scheduled_for DESC LIMIT 1)
    AS latest_writer_error,
  (SELECT substring(value::text,1,200) FROM settings WHERE key='council_failure')
    AS latest_council_failure;
```

**Read it like this:**
- `scripts_written_last_hour > 0` → **the keys fixed it.** Batch #2 shifts from rescue to hardening — the
  ladder floor and escalation still ship, but as insurance rather than emergency.
- Error still shows only `gemini | groq` → the OpenRouter rungs are still being dropped by `_providers()`;
  REQ-LADDER-FLOOR becomes urgent and the diagnostic narrows to `_llm._has_key('openrouter')` vs
  `provider_state('openrouter')`.
- Error now lists **five** providers → the ladder is fully engaged and genuinely exhausted; **paid
  escalation (REQ-ESCALATE-1) is the only remaining unblock**, and it becomes rank 1.

Send me the output and I will scope Batch #2 to whichever of the three cases is true.
