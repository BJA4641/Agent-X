# OVERNIGHT RUN-SHEET — Agent-X v6.0 sprint

What tonight actually is: we BUILD phases 0-3 completely. Phases 4-8 are
gated on real-world data (Meta review, live posts, days of metrics) that
no amount of overnight coding creates. Anyone who tells you otherwise is
writing the next fake handoff.

## BATCH 1 — this zip (do these NOW, ~20 min, no source code needed)

1. Upload this zip's contents to the repo via GitHub web UI:
   - `web/app/api/cron/health/route.ts`  (watchdog)
   - `web/vercel.json`                    (5-min cron — if you already have a
     vercel.json, merge the "crons" block into it instead of replacing)
   - `.github/workflows/test.yml`         (CI gate)
2. Run `db/v6.0_BATCH1_EMERGENCY_REPAIR.sql` in Supabase SQL Editor.
   ⚠ All accounts get PAUSED by this script. That is intentional —
   do not unpause anything until Batch 2 is deployed.
3. Run `db/v6.0_BATCH1_SECURITY_RLS.sql` in Supabase SQL Editor.
   Then: Supabase Dashboard → Settings → API → Reset **anon** key →
   update NEXT_PUBLIC_SUPABASE_ANON_KEY on Vercel.
4. Vercel env vars: add `ALERT_WEBHOOK_URL` (make a Discord webhook:
   any server → Settings → Integrations → Webhooks → New → Copy URL).
   Confirm `DAILY_BUDGET_USD` is set on Vercel too (watchdog reads it).
5. Verify: open `https://agent-x-two.vercel.app/api/cron/health` in the
   browser. You should see JSON with `heartbeat_age_min`, `spend_24h_usd`,
   etc. If alerts fire immediately about the worker — expected, the
   pipeline is still broken until Batch 2.

## YOUR PARALLEL TASKS TONIGHT (signups — do while I build Batch 2)

| Task | Where | Time | Unlocks |
|---|---|---|---|
| Gemini API key | aistudio.google.com | 5 min | Free text+images baseline |
| FAL key | fal.ai (Google/GitHub signin → API Keys) | 5 min | Flux images, $5 free credit |
| ElevenLabs key | elevenlabs.io → Profile → API key | 10 min | Real voice (~$5/mo starter) |
| Groq key | console.groq.com | 5 min | Free fast text fallback |
| Invent REVENUE_WEBHOOK_SECRET | random password | 1 min | Locks the revenue pixel |
| Amazon Associates signup | affiliate-program.amazon.com | 30 min | Starts the 180-day clock |
| START Meta app (IG) | developers.facebook.com → Create App → add Instagram Graph API | 30-60 min | The venture's true critical path. May need review time — start it TONIGHT even though approval may take days. |

Add the keys to **Railway** env vars as you get them:
GEMINI_API_KEY, FAL_KEY, ELEVEN_API_KEY, GROQ_API_KEY, REVENUE_WEBHOOK_SECRET.
(Skip OpenAI / BFL / GOAPI / DeepSeek / OpenRouter — not needed yet.)

## BATCH 2 — built next, against your uploaded source zip

Requires: you upload `Agent-X-v5.5.1-UPGRADE.zip` (or current repo zip)
to this chat. Contents of Batch 2:

- **THE FIX**: brain.py accepts `grade_feedback`; creative.py call hardened
- Repeated-failure circuit breaker (5 identical fails → pause job_type +
  critical recommendation + upstream stop)
- Ideation backpressure (skip ideate when >10 unconsumed ideas)
- Worker-side no-output kill switch (spend without output → auto killswitch)
- Mandatory REVENUE_WEBHOOK_SECRET on /api/revenue/track (403 when unset)
- ElevenLabs wiring: voice.py → aisuite.tts with logged fallback,
  voiceover caching by script hash, daily character cap
- Quality floor: gradient-visuals or fallback-voice → human_desk, not publish
- Contract tests (call real functions with real kwargs) + the ONE true
  pipeline dry-run test + failure-path tests
- Sidebar "Monetize" → "Sell & earn" (finally)
- Purge of placeholder-derived lessons + post_mortem disabled until real
  metrics (Batch 3)

## BATCH 3 — also buildable tonight (code-complete, verifies later)

- Real IG metrics pull (activates when IG token lands)
- `/go/[slug]` affiliate click tracker + subscribers table + capture form
- YT Shorts publish path check
- `/api/version` endpoint + footer version chip

## OVERNIGHT SUCCESS = 

Batch 1 deployed ✚ Batch 2 deployed ✚ CI green ✚ ONE account unpaused ✚
watchdog quiet ✚ first board_item ever reaches `approved` while you sleep.
Then tomorrow: eyeball the content, finish the Meta app, and Phase 2's
"first 10 supervised publishes" begins. That's the honest overnight win.
