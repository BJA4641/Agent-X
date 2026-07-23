# CHANGELOG — v5.9.6 "LADDER FLOOR + ESCALATION"
**Released:** 2026-07-24 · **Batch:** Roadmap Batch 1 (Phase 0 — "First Post")
**Previous:** v5.9.5 (demand governor, SLA engine, fair claiming, $0 paused prep)
**Verification:** 123/123 tests pass · boot_check OK (70 modules) · every touched file compiles

---

## WHY THIS RELEASE EXISTS

The platform had published **zero items in its entire history** despite 39,150 completed jobs and a
funded wallet. The 2026-07-24 audit traced it to two defects on the critical path:

1. `council._order()` **replaced** the hardcoded 5-rung free-model ladder with whatever
   `strategy.arena_scout` last wrote to `settings.free_council_models`. An arena run wrote a 2-rung
   ladder; the three OpenRouter fallbacks silently vanished.
2. When those two rungs died (Gemini `429`, expired Groq key `403`), the writer's ladder ended at
   **"delay 30 minutes"** — there was no rung that escalates to a paid model. The factory idled
   forever with **$23.85 of a $25/account/month cap unused**.

An autonomous agent narrowed the platform's own safety net, and nothing reported it. This release
fixes both the instance and the class.

---

## CHANGES BY FILE

### `agentcore/council.py` — REQ-LADDER-FLOOR (WSJF 39.0), REQ-DIAG-1
- **NEW `merge_ladder(picked, floor)`** — pure, unit-tested. Arena picks come first, then every
  hardcoded `_FREE_ORDER` rung not already present is appended, deduped. **The floor can no longer be
  removed by an autonomous agent — only re-ordered.**
- `_order()` now calls `merge_ladder()`; the `return picked` early-exit that caused the outage is gone.
- `_providers(explain=True)` returns *why* each rung was dropped (`no key`, `state=rate_limited`).
- **NEW `ladder_report()`** — operator snapshot: usable rungs, dropped rungs with reasons, `below_floor` flag.
- `free_chat()` failure detail now names rungs that were **never attempted**, plus
  `attempted=N usable_rungs=M`. Previously a ladder silently narrowed to 2 was indistinguishable
  from a 5-rung ladder that genuinely failed 5 times.
- `NEW LADDER_FLOOR_MIN = 3`.
- Backward compatible: `_providers()` without arguments behaves exactly as before.

### `workers/departments/creative.py` — REQ-ESCALATE-1, REQ-DIAG-1
- **NEW `escalation_allowed(...)`** — pure decision function (DEC-028). All guards must pass
  (kill switch, cost mode, daily budget, $25/account monthly cap), then at least one justification
  must hold (SLA `at_risk`/`behind`/`breached`, **or** nothing published today).
- **NEW `_escalate_to_paid(...)`** — on free exhaustion, requests permission, asks the CEO gate, then
  makes **exactly one** paid attempt. Delay is now the **last** resort, not the second.
- **NEW `_sla_state_for(...)`** — reads `settings.sla_status` for deadline pressure.
- Job error truncation widened `[:150]` → `[:900]`. The old limit cut the provider list mid-word and
  destroyed the evidence needed to diagnose this very outage.
- Module-level `_brain` handle so the escalation path has one patchable reference.
- **NEW env:** `ESCALATION_ENABLED` (default `1`), `ESCALATION_EST_USD` (default `0.02`).

### `workers/departments/portfolio.py` — REQ-GOV-2, REQ-DEDUPE-1
- `_count_inflight()` ignores items older than `INFLIGHT_MAX_AGE_H` (default **6h**, must exceed
  `STALE_IDEA_HOURS` so the sweep gets first rescue attempt). Fixes the observed deadlock:
  *"quota met (0 produced + 2 in-flight ≥ 1) — no ideation"* while output was zero.
- Age filter applied defensively — a client without `.gte()` falls back to the un-aged count, never to 0.
- Re-plan spawn now carries `idempotency_key=replan:{item_id}`. One topic had been queued **5×**;
  harmless while the writer was dead, a 5× spend multiplier the moment escalation lands.
- **NEW env:** `INFLIGHT_MAX_AGE_H` (default `6`).

### `workers/departments/sla.py` — REQ-SLA-TZ
- **NEW `resolve_deadline_utc(deadline_local, tzname, day)`** and **`account_deadline_utc(acct, day)`**.
- Default deadline is now **14:00 Asia/Dubai** per the founder mandate (v5.9.5 shipped 08:00–22:00 UTC —
  the wrong deadline entirely). Per-account override via `project_accounts.config.sla_deadline` /
  `config.sla_timezone`. Falls back to a fixed offset table when `zoneinfo` data is unavailable.
- `plan_day` now records `deadline_utc`, `deadline_local` and `timezone` per account.
- **NEW env:** `SLA_DEADLINE_LOCAL` (`14:00`), `SLA_TIMEZONE` (`Asia/Dubai`), `SLA_WINDOW_START_H` (`6`).

### `workers/departments/ops.py` — REQ-HEALTH-1
- **NEW `start_heartbeat_pulse(...)`** — a **daemon thread** writes `worker_health` every 20s.
  Root cause: the worker is single-threaded, so a slow LLM call blocked the loop *and* the queued
  `ops.heartbeat` job — `worker_health` went 10+ minutes stale and the dashboard declared a healthy
  worker dead. Liveness must not be reported by the same queue whose blockage it detects.
- The `ops.heartbeat` job is retained as fallback and for job-count accuracy.
- Telemetry failures are swallowed — the pulse can never crash the worker.

### `workers/departments/paused_prep.py` — REQ-PREPOBS-1
- **NEW `_record_skip(...)`** — a $0 skip is still a skip, but never silent: emits an event and writes
  `settings.prep_last_skip`. v5.9.5 banked 0 items every cycle and reported nothing, so a dead free
  tier looked identical to "nothing to do".
- **The $0 guarantee is unchanged and still test-enforced** (DEC-024).

### `workers/runner.py`
- `VERSION` → **5.9.6** (history comment preserved).
- Starts the heartbeat pulse thread at boot, non-fatally.

### `tests/test_v596_escalation.py` — NEW (27 tests, incl. REQ-E2E-1)
- Ladder floor: survives a narrow arena write, arena-first ordering, dedupe, malformed entries, source-level
  assertion that `_order` can never return arena picks alone.
- Escalation: every guard blocks; every justification permits; **guards outrank justifications**
  (a breached SLA cannot punch through the kill switch or the $25 cap); source assertion that escalation
  is attempted before the delay.
- **End-to-end (REQ-E2E-1):** drives the writer with all free providers failing and asserts a script is
  produced via exactly ONE paid attempt — plus the inverse, that the kill switch prevents any paid call.
  **Before v5.9.6 this test fails, which is precisely the point.**
- Diagnostics, in-flight age-out, replan idempotency, SLA timezone maths, prep-skip visibility,
  heartbeat daemon.

---

## MIGRATION INSTRUCTIONS

1. **Upload** the 8 changed files + 1 new test, preserving paths, via the GitHub web UI. CI runs
   automatically on push to `main`; **if the tests badge is red, do not deploy.**
2. **No database migration required.** No schema changes. New state lands in existing `settings` rows
   (`free_ladder_report`, `prep_last_skip`) and existing `project_accounts.config` keys.
3. **No new environment variables are required.** All six new vars have working defaults. Optional tuning:

   | Var | Default | Purpose |
   |---|---|---|
   | `ESCALATION_ENABLED` | `1` | Set `0` for an instant, code-free rollback of paid escalation |
   | `ESCALATION_EST_USD` | `0.02` | Estimated cost used in budget pre-checks |
   | `INFLIGHT_MAX_AGE_H` | `6` | Age after which a stalled item stops counting as in-flight |
   | `SLA_DEADLINE_LOCAL` | `14:00` | Daily publish deadline (local time) |
   | `SLA_TIMEZONE` | `Asia/Dubai` | Timezone for the deadline |
   | `SLA_WINDOW_START_H` | `6` | Hours before deadline the production window opens |

4. **Verify after Railway redeploys** (boot log should print `5.9.6` and `heartbeat pulse thread started`):

```sql
SELECT
  (SELECT count(*) FROM board_items WHERE status IN ('drafted','approved','scheduled','published')) AS items_past_idea,
  (SELECT count(*) FROM jobs WHERE job_type='creative.write_script' AND status='done'
     AND created_at > extract(epoch from now())-3600)                     AS scripts_last_hour,
  (SELECT round((extract(epoch from now()) - last_heartbeat_at)::numeric,0) FROM worker_health) AS hb_lag_s,
  (SELECT substring(value::text,1,300) FROM settings WHERE key='free_ladder_report') AS ladder,
  (SELECT substring(coalesce(error,'none'),1,300) FROM jobs
     WHERE job_type='creative.write_script' ORDER BY scheduled_for DESC LIMIT 1) AS latest_writer_error;
```
   **Expected:** `hb_lag_s` < 60 (was 624). `latest_writer_error` now lists **five** providers or
   shows an escalation result instead of a bare two-provider failure. `items_past_idea` > 0 within
   ~30 minutes — **the first content in the platform's history to pass the writer.**

5. **Rollback:** set `ESCALATION_ENABLED=0` (disables paid escalation only) or redeploy the previous
   commit. No data migration to reverse.

---

## BACKWARD COMPATIBILITY
- No schema changes, no removed functions, no changed job types or payload contracts.
- `_providers()` retains its original zero-argument signature.
- The `ops.heartbeat` job chain is unchanged and still runs.
- All 96 pre-existing tests pass unmodified; 27 added.

## KNOWN LIMITATIONS (carried in the roadmap, not fixed here)
- Execution is still **single-threaded** (`claim(limit=1)`) — REQ-PARALLEL-1, Phase 2.
- Publishing OAuth incomplete: approved content still cannot post — REQ-PUB-TOKENS, Phase 1, 🔴 founder.
- Human approval remains in every publish path — REQ-AUTOAPPROVE-1, Phase 1.
- Self-maintenance is still ~97% of queue volume — REQ-OVERHEAD-2, Phase 3.
