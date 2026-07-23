# Agent-X v5.9.2 — WHY THE WRITER DIES, AND THE READABILITY PASS

`77 passed` · `npm run build` clean. Deploy on top of v5.9.1.

---

## 1. I was wrong about the model names

I said `gemini-2.5-flash` was stale. It is not — the live discovery list shows it,
and `llama-3.3-70b-versatile` is live on Groq too. Good theory, wrong.

The real cause is in `agent/llm.py`:

```python
body = {"contents":[...], "generationConfig": {"maxOutputTokens": max_tokens}}
text = "".join(p.get("text","") for p in data["candidates"][0]["content"]["parts"])
```

**Gemini 2.5+ thinks by default, and the reasoning tokens are charged against
`maxOutputTokens`.** With a 1800-token budget on a long branded prompt, the model
spends the budget thinking, returns `finishReason: MAX_TOKENS`, and emits a
candidate with **no `parts` key at all**. That line then throws `KeyError`, the
council swallowed it, and every draft reported the same useless sentence:

> no model produced a script (council+fallback failed)

Fixed: thinking disabled for drafting (`thinkingConfig.thinkingBudget = 0`), a
2048-token floor, graceful retry for older models that reject the field, and
explicit errors naming `finishReason` instead of a KeyError.

## 2. The diagnostic gap that cost us today

The council kept only the **last** exception. Three providers could fail for three
different reasons and you would see one opaque line. Now every provider's own
error is collected, raised together, written to `settings.council_last_failure`,
and emitted to the feed as a Writer error:

```
⚠️ every free model failed — gemini/gemini-2.5-flash: empty text (finishReason=MAX_TOKENS)
   | groq/llama-3.3-70b-versatile: HTTP 401 | openrouter/...:free: 429 rate limited
```

That is the difference between another hour of guessing and a one-line answer.

## 3. Why your live accounts had no documents

I generated 800 documents for the 100 accounts that had **none**. The five that
already had rows were skipped — including both live accounts. Their existing docs
came from the old architect agent and averaged **130 characters**:

| account | before | after |
|---|---|---|
| glowup.daily | 13 docs, 1 of 5 core, avg 130 chars | 17 docs, **5 of 5 core**, avg 715 |
| puppy.parent | 13 docs, 1 of 5 core, avg 129 chars | 17 docs, **5 of 5 core**, avg 704 |

**Already applied to production.** Adapted from their niche siblings with their
own positioning, so they do not read as clones. That is also the honest answer to
"are we still counting on the slow turtle agents" — for those two accounts, yes,
we were. Not any more.

## 4. "Worker is not beating" while the worker was fine

`worker_health` upsert had no `on_conflict` target, so a changed `worker_id` could
write a second row or fail while jobs kept completing normally. The banner was
reporting a stale row, not a dead worker. Now pinned to `on_conflict="worker_id"`.

## 5. Typography & density pass

- `--dim` was `#9AA3AF` on `#101318` ≈ **4.4:1** — under the 4.5:1 AA floor, and it
  was the colour of every `.note`, `.card p` and `.lead` at 12–14px. Now `#B6BFCC`
  (~7:1). Light theme fixed the same way.
- `h1` was `clamp(34px, 5.4vw, 58px)` — landing-page scale on dashboards. Now 28px
  inside the app shell.
- `.wrap` capped content at **1080px** while the shell also carries a 208px sidebar
  and a 320px rail — roughly 500px of usable column. Shell now 1400px.
- Body 14px / line-height 1.45 inside the app (1.55 stays for prose).
- Sidebar: quieter section labels, tighter rows, a real active state with an accent
  bar. Focus rings added — there were none over the dark background.
- Tabular numerals so metrics line up.

---

## Files (15)

```
pipeline/agent/llm.py                     Gemini thinking-budget fix
pipeline/agentcore/council.py             per-provider error reporting
pipeline/workers/departments/ops.py       heartbeat on_conflict
pipeline/workers/runner.py                VERSION 5.9.2
web/app/globals.css                       typography + density + a11y
web/app/api/version/route.ts              WEB_VERSION 5.9.2
(+ v5.9.1 files carried forward)
```

## After deploying — the one thing to check

Open Agent workspace and filter to **Writer**. Within a tick you will see either a
script, or a line naming exactly which provider failed and why. Send me that line.
