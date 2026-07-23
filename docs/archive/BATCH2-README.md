# BATCH 2 — v5.6.0: the production fix

Built against your uploaded source (`Agent-X-main`), every changed file
`py_compile`-verified, full test suite green: **40/40** (33 existing +
7 new contract tests that actually CALL the functions).

## What was broken (three real bugs found in your source)

1. **THE outage** — `creative.py` passes `grade_feedback=` to
   `brain.write_script()`, which didn't accept it. TypeError × 7,220 over
   63 hours. → brain.py now accepts it and merges job feedback (the CQO's
   concrete fix list) with memory feedback, job feedback first.
2. **The idea flood** — `portfolio._count_inflight` chained
   `.eq("status","idea").or_(...)` which supabase-py combines as AND →
   matched **zero rows** → the in-flight cap never engaged → 7,307 ideas.
   → replaced with `.in_("status", [idea, drafted, approved, scheduled])`.
3. **ElevenLabs never fired** — docs told you to set `ELEVEN_API_KEY`;
   the code read `ELEVENLABS_API_KEY`. → both names accepted everywhere now.

## What's new

- **Circuit breaker** (worker.py): 5 identical consecutive failures on a
  job type → that job type is paused 30 min, critical event + CEO
  recommendation written. A repeat of the outage now stops itself in
  ~2 minutes instead of 63 hours.
- **No-output auto kill switch** (portfolio.py): >$0.50 spent since worker
  boot with ZERO items reaching approved/scheduled/published (15-min boot
  grace) → kill switch flips itself on, critical alert + recommendation.
  Money can no longer burn against a broken pipeline.
- **ElevenLabs with timed captions** (voice.py + captions.py): premium
  narration now uses the `/with-timestamps` endpoint so word-level caption
  sync works with Eleven audio. Daily character cap
  (`ELEVEN_DAILY_CHAR_CAP`, default 10,000 ≈ $1.50) so voice can't eat the
  budget. Falls back to edge-tts, then silent — every fallback logged, and
  the engine used (`elevenlabs` / `edge` / `silent`) is stamped on the
  board item as `voice_engine` for the Batch 3 quality floor.
- **Revenue endpoint locked**: `REVENUE_WEBHOOK_SECRET` is now mandatory —
  unset returns 503, wrong secret 401. Fake-revenue budget steering closed.
- **Contract tests** (`tests/test_v6_contracts.py`): real invocation of
  `write_script(grade_feedback=...)` (fails on v5.5.1, passes now),
  inflight-filter behavior, breaker trip behavior, env alias, char cap.
  CI (Batch 1) runs these on every push.
- Version banner → **5.6.0**.

## Files in this zip (complete replacements, drag into repo root)

```
pipeline/agent/brain.py
pipeline/agent/config.py
pipeline/agent/voice.py
pipeline/agent/captions.py
pipeline/workers/departments/creative.py
pipeline/workers/departments/portfolio.py
pipeline/agentcore/worker.py
pipeline/workers/runner.py
pipeline/tests/test_v6_contracts.py        (new)
web/app/api/revenue/track/route.ts
db/v6.0_BATCH2_EMERGENCY_REPAIR_FIXED.sql  (new — replaces failed Batch 1 SQL)
```

## DEPLOY STEPS — in this exact order

1. **Upload this zip's files to GitHub** (web UI, replace existing).
   Railway and Vercel auto-redeploy. Wait for Railway deploy to finish.
2. **Railway logs**: confirm the boot banner says **5.6.0**.
3. **Supabase SQL Editor**: run `db/v6.0_BATCH2_EMERGENCY_REPAIR_FIXED.sql`.
   Check the verification output at the bottom (idea = 0, active = 0).
4. **Railway variables — add:**
   - `ELEVEN_API_KEY` = your ElevenLabs key (or `ELEVENLABS_API_KEY`, both work now)
   - `GROQ_API_KEY` = optional free text fallback (console.groq.com)
5. **Vercel variables — add** (Settings → Environment Variables → all envs):
   - `REVENUE_WEBHOOK_SECRET` = same value as on Railway
   - `DAILY_BUDGET_USD` = same value as on Railway
   Then redeploy web (Deployments → ⋯ → Redeploy).
6. **Railway billing**: you have **$4.55 of trial credit left**. Add a card
   / Hobby plan now — when it hits $0 the worker dies silently and no code
   can save you.
7. **Unpause exactly ONE account** (dashboard → project → account → resume).
8. **Watch for 30 min**: activity feed should show scout → ideate →
   write_script ✍️ → grade → render, and the first board_item in history
   should reach **approved**. If anything loops, the breaker or the auto
   kill switch will stop it and tell you — that's the system working.

## What I did NOT do (on purpose, said out loud)

- Quality-floor ENFORCEMENT (fallback voice/visuals → human review instead
  of publish) — engine metadata is stamped now; the routing gate lands in
  Batch 3 once we've watched one item flow end-to-end.
- Prompt/behavior changes — tonight is stability only. One variable at a time.
