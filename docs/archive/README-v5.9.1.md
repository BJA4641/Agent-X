# Agent-X v5.9.1 — THE WRITER FINALLY RUNS

Deploy on top of v5.9.0. `77 passed` · `npm run build` clean.

v5.9.0's event feed fix paid off immediately — the agents told us what was wrong
within minutes. This release fixes everything they reported.

---

## 1. The deadlock, in their own words

```
15:05  ceo  👔 tick — account: Glow Up Daily (@glowup.daily)
15:05  coo  in-flight for @glowup.daily: 4/2, daily target 1
15:05  coo  @glowup.daily in-flight at cap — no new reels this tick
```

`_count_inflight()` counted the **entire board** but compared it against
`MAX_INFLIGHT_PER_ACCOUNT = 2`. Four stale ideas from 12:03 therefore blocked
every account permanently. `board_items` does carry `account_id` here, so the
count is now scoped per account.

**Also: my budget theory was wrong.** `effective_config` reported
`daily_budget_usd: 3` against $1.136 spent. Publishing that value is what ruled
it out — worth the extra field.

## 2. Stale ideas could deadlock forever

`editorial.ideate` creates an idea and enqueues `editorial.plan_one` to draft it.
If that chain dies mid-flight the idea sits at `idea` forever, occupying an
in-flight slot, with no error and no event. New `_sweep_stale_ideas()`: any idea
older than 2h gets one re-plan attempt, then is cleared.

## 3. My own bug from v5.8.8

The v5.8.8 spend-policy patch rewrote three budget gates in `creative.py` with a
blanket `may_spend_on('image', ...)` — including **script writing**, which is
thinking, not art. Labelling it `'text'` would have been worse: under the policy
that returns `False` and would have delayed every script by an hour, forever.
Correct behaviour, now shipped: a script written by the free council needs no
paid-budget gate at all.

## 4. My probe was reporting false failures — and acting on them

| provider | probe said | truth |
|---|---|---|
| groq | BAD KEY (code 1010) | Cloudflare rejected urllib's User-Agent |
| fal | HTTP 404 | I probed `fal.run/health`, which does not exist |
| elevenlabs | BAD KEY | key works; it just lacks the `user_read` scope |

Worse, the probe called `costmode.mark_error()` on those failures — putting
**working providers into a 24h cooldown** and shrinking the free council. A probe
is a diagnostic; it must never cool down a provider. Only real production call
failures do that now. Browser User-Agent added, fal endpoint corrected,
scope errors classified as `needs_scope` rather than a dead key.

Real findings that stand: **openrouter $0.00** and **deepseek $0.00**.

## 5. Why the writer still failed — stale model names

With the board unblocked the writer finally ran, and died:

```
creative.write_script: "no model produced a script (council+fallback failed)"
```

Every key validated. The council was asking for **`gemini-2.5-flash`** — a name
two generations stale (the arena board today lists gemini-3.6-flash, 3.1-pro,
3-pro). Hardcoded model IDs rot silently.

Fix: `providers.probe` now records the model IDs each vendor **actually serves**
into `settings.provider_models`, and the council resolves its preference against
that list by prefix. `gemini-2.5-flash` becomes whatever flash model exists
today. OpenRouter always resolves to a `:free` route. If discovery has not run
yet the original name passes through unchanged.

This is the class of bug worth killing permanently: **discover, don't hardcode.**

---

## Files (12)

```
pipeline/agentcore/council.py               live model resolution + cooldown-aware
pipeline/agentcore/costmode.py              free_text_available()
pipeline/agentcore/events.py                (v5.9.0 persister fix, included)
pipeline/workers/departments/portfolio.py   per-account cap + stale-idea sweeper
pipeline/workers/departments/providers.py   model discovery, no cooldowns, real endpoints
pipeline/workers/departments/creative.py    script write no longer gated on paid budget
pipeline/workers/departments/strategy.py    (arity fix, included)
pipeline/workers/runner.py                  VERSION 5.9.1
pipeline/tests/*                            77 tests
web/app/api/version/route.ts                WEB_VERSION 5.9.1
```

## Already applied to production (no deploy needed)

- The 4 stale ideas are cleared — the board unblocked and immediately produced
  4 new ideas → 4 plans → 4 write_script jobs.
- The bogus groq / fal / elevenlabs cooldowns are lifted.

## After deploying

1. `providers.probe` runs at boot and writes `settings.provider_models`.
2. The council resolves to a live Gemini model and the writer should produce its
   first script. Watch Agent workspace for a **Writer** event.
3. If it still fails, the error is now specific and visible — send it to me.
