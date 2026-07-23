# Agent-X v5.8.8 — NEVER STOPS · SPEND POLICY · LIVE PROVIDER STATUS

One upload. Contains v5.8.7 (never-stop + provider visibility) and v5.8.8
(spend policy + arena scout). `66 passed` pytest · `npm run build` clean.

---

## 1. Why the worker was doing nothing

Two separate faults, both fixed.

**(a) The kill switch was still on.** `no_output_guard` had written
`{"on":true}` and nothing cleared it. **Already cleared in Supabase** — you did
not need this deploy for that part.

**(b) The real bug — free work was gated behind the PAID budget.**

```python
if llm.ready() and ledger.budget_ok(EST_COST):   # brain.py — blocked EVERYTHING
```

The free council costs **$0**, but it sat behind the paid budget check. The
moment your $1.50 daily budget was gone, the writer stopped completely while
free models sat idle. Same in the grader and the rewrite path.

Now: free work never asks the paid budget. Only paid calls go through
`costmode.may_spend()`.

**(c) The guard no longer hard-stops.** It degrades to `free_only`: paid
suspended, free keeps producing at $0, and paid restores itself automatically at
the next budget day. A hard stop only fires if money still leaks *while in
free-only* — which means something is charging outside the router.

---

## 2. Your spend policy, enforced in code

> "Paid money only on art creation, nothing on strategy. Once every 10 days
> Anthropic evaluates the period and trains the agents."

`agentcore/costmode.py`:

```python
ART_CATEGORIES      = image, video, voice, audio, ...   -> paid ALLOWED
THINKING_CATEGORIES = text, strategy, grading, writing  -> FREE ONLY, always
strategy_audit_days = 10                                -> the one exception
```

- `creative.py` art spends now route through `may_spend_on('image', usd)`.
- **The per-item Claude audit from v5.8.6 is now OFF by default.** It was paid
  thinking (~$0.01/item), which your policy forbids. That budget moves to the
  retro. Re-enable with `settings.claude_final_audit = {"on": true}`.
- `strategy.audit` — the ONLY paid thinking call. Every 10 days Claude reads the
  period (items by status, spend by model, grader lessons) and writes up to 6
  concrete lessons into `agent_lessons`, which the free writers and graders read
  on every subsequent draft. One call, roughly $0.05 per cycle.

Change the policy without a deploy:
```sql
insert into settings(tenant_id,key,value) values
('me','spend_policy','{"paid_art":true,"paid_thinking":false,"strategy_audit_days":10}')
on conflict (tenant_id,key) do update set value=excluded.value;
```

---

## 3. The free council was pointed at a dead model

`council.py` listed `moonshotai/kimi-k2:free`. **That route no longer exists** —
verified against OpenRouter's live `/api/v1/models`. Every draft sent there
failed and fell through to paid Claude. That is a large part of your $1.14.

Only **14** free routes exist on OpenRouter today. New rotation, all verified live:

| # | provider | model | why |
|---|---|---|---|
| 1 | gemini | gemini-2.5-flash | own free tier, most generous |
| 2 | groq | llama-3.3-70b-versatile | own free tier, fastest |
| 3 | openrouter | `google/gemma-4-31b-it:free` | Apache-2.0, arena #52 overall / top-10 open-weight, 262k ctx |
| 4 | openrouter | `nvidia/nemotron-3-ultra-550b-a55b:free` | 550B free |
| 5 | openrouter | `openai/gpt-oss-20b:free` | free |

The council also skips any provider in cooldown, so a rate-limited free model
hands off to the next instead of falling through to paid.

---

## 4. Arena leaderboard scout (`strategy.arena_scout`)

Runs on boot and weekly. Parses the **live** arena.ai boards — text,
text-to-image, text-to-video, image-to-video, image-edit — and stores them in
`settings.arena_rankings`. It then rewrites `settings.free_council_models`, so
the debate roster follows the leaderboard **without a redeploy**.

Verified working against the live site today. Top open-weight text models right now:

```
#29 glm-5.1              1469.6  MIT
#30 glm-5.2 (max)        1469.2  MIT
#34 mimo-v2.5-pro        1466.8  MIT
#39 kimi-k2.6            1460.9  Modified MIT
#46 deepseek-v4-pro      1456.6  MIT
#52 gemma-4-31b          1450.8  Apache 2.0   <- the only one free on OpenRouter
```

Honest limit: arena.ai has no API. This parses the page's embedded data payload.
If they change their markup the scout stores `[]` plus a note — it never invents
rankings, and the previous roster stays in place.

---

## 5. Live provider status + balances (`providers.probe`)

Boot + every 6h. New panel at the top of **AI models**.

**Balance is real where the vendor publishes one:**
OpenRouter `/api/v1/credits` · DeepSeek `/user/balance` · ElevenLabs
`/v1/user/subscription` (characters) · Stability `/v1/user/balance`

**No balance API exists for:** OpenAI (confirmed — the old billing endpoint is
gone with no replacement), Anthropic, Gemini, Groq, FAL, BFL, Ideogram, Recraft,
GoAPI, Replicate. For these the probe validates the key is alive and shows *our
own measured spend* from `run_ledger`. The UI says "no balance API" rather than
showing a fake zero.

Statuses: **LIVE · LINKED · OUT OF CREDIT · BAD KEY · RATE LIMITED · NOT CONNECTED**.
A 402/401/429 sets a cooldown (12h / 24h / 15m) so the router skips that provider
instead of failing the job.

---

## 6. Live-build banner

Dismissible strip at the top of every page: web version, worker version,
heartbeat age, git commit, and a FREE-ONLY badge when paid is suspended.
Dismissal is keyed to the build stamp, so **it reappears on every new deploy** —
one confirmation per push, which is what you asked for.

Green = web and worker agree · amber = versions disagree (deploy still rolling)
· red = worker not beating.

---

## 7. Also fixed

- **DeepSeek retires `deepseek-chat` / `deepseek-reasoner` tomorrow (July 24).**
  Added `deepseek-v4-flash` / `deepseek-v4-pro` ahead of them; old IDs kept as
  last-resort fallbacks and marked deprecated.
- **Key aliases.** The inventory reported `ELEVENLABS_API_KEY` missing while you
  have `ELEVEN_API_KEY`. Voice always worked; the dashboard was lying. Now
  alias-aware (also `YT_API_KEY`/`YOUTUBE_API_KEY`, `FAL_KEY`/`FAL_API_KEY`).

---

## Files (21)

```
pipeline/agentcore/costmode.py              NEW — cost mode + spend policy + provider health
pipeline/agentcore/council.py               free rotation fixed, cooldown-aware, DB-overridable
pipeline/agentcore/aisuite.py               router skips dead/out-of-credit; classifies 402/401/429
pipeline/agentcore/providers_catalog.json   DeepSeek V4, Gemini-first tiers, Claude last
pipeline/agent/brain.py                     free writing no longer gated on paid budget
pipeline/agent/grader.py                    free grading + rewrite no longer gated on paid budget
pipeline/workers/departments/strategy.py    NEW — 10-day paid audit + arena scout
pipeline/workers/departments/providers.py   NEW — key/liveness/balance probe
pipeline/workers/departments/portfolio.py   guard degrades to free_only instead of stopping
pipeline/workers/departments/creative.py    art spend through the policy gate
pipeline/workers/departments/cqo.py         per-item Claude audit off by default
pipeline/workers/departments/__init__.py    registers providers + strategy
pipeline/workers/runner.py                  VERSION 5.8.8, boot probe + scout + audit, alias inventory
pipeline/tests/test_v587_costmode.py        NEW — 7 tests
pipeline/tests/test_v582_council.py         mock updated
web/components/VersionBanner.tsx            NEW
web/components/ProviderStatus.tsx           NEW
web/app/layout.tsx                          mounts the banner
web/app/api/version/route.ts                web 5.8.7 + commit + cost_mode
web/app/api/ai-models/route.ts              exposes provider_status / inventory / cost_mode
web/app/dashboard/models/page.tsx           renders the provider panel
```

## Deploy

1. Upload the zip to GitHub → Railway + Vercel rebuild.
2. Banner should read **web v5.8.7 · worker v5.8.8**. (Web and worker version
   independently; amber for a minute during rollout is normal.)
3. Within ~2 min the AI models page fills with live provider status.
4. Watch `run_ledger`: `brain` and `grader` rows should read `free:...`.
   The only Anthropic line should be `strategy.audit`, once per 10 days.

## Still worth doing (not code)

- Add `TENANT_ID` to Vercel — the web app defaults to `"me"`; if Railway differs
  the two read different settings rows.
- Verify `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`,
  `GEMINI_API_KEY`, `GROQ_API_KEY`, `FAL_KEY` are scoped to **Production** in
  Vercel — your list showed them as Preview-only.
