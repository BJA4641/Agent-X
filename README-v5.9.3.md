# Agent-X v5.9.3 — I BROKE THREE FEATURES WITH ONE INVENTED FUNCTION

`80 passed` · `npm run build` clean.

---

## What I got wrong

In v5.9.1 and v5.9.2 I wrote `runtime.supabase()` and `runtime.bus()` in three
places. **Neither function exists.** `runtime.py` only exposes `get_runtime()`.

Every call raised `AttributeError` inside a bare `except: pass`, so three
features I told you were shipped have been silently dead the whole time:

| feature | claimed | actual |
|---|---|---|
| live model discovery (`_live_models`) | resolves stale model names | returned `{}` — never applied |
| arena free-council roster (`_order`) | roster follows the leaderboard | returned the hardcoded default |
| per-provider failure reporting | tells you which model failed and why | wrote nothing, logged nothing |

That is why you ran v5.9.2, the writer failed, and you *still* got the same
useless sentence. You were right to be annoyed.

All three now use `costmode._sb()`, the accessor that actually works (it has a
`create_client` fallback, which is why costmode kept working while these did not).

Three new tests assert that nobody calls a runtime helper that does not exist,
that the council uses the working accessor, and that brain never re-introduces
the generic message.

## brain.py threw the reason away

```python
except Exception as e:
    ledger.record("brain", ..., detail=str(e)[:300])   # kept
...
raise RuntimeError("writer: no model produced a script (council+fallback failed)")
```

The real error went to the ledger; the raise discarded it. Now:

```
writer: no script — gemini/gemini-2.5-flash: empty text (finishReason=MAX_TOKENS)
  | groq/llama-3.3-70b-versatile: HTTP 401 ...
```

## "Worker is not beating" — the actual cause

The worker was **never down**. `ops.heartbeat` had one job stuck `in_progress`
since 15:18. Each heartbeat enqueues the next one, so a single orphaned job kills
the chain permanently while every other job type keeps running normally.

- Cleared in production already.
- v5.9.3 reaps orphaned `in_progress` jobs at boot so it cannot recur.
- Your banner also showed `worker v5.8.8` while the database said `5.9.2` — that
  is a cached page. Hard-refresh (Ctrl+Shift+R).

## Also applied to production (no deploy needed)

- `puppy.parent` promoted from `needs_setup` → `ready` (it has all 5 core docs now,
  so the "queued" label was stale — `needs_setup` renders as "queued").
- The 4 parked `write_script` jobs were released from retry backoff.

---

## Files

```
pipeline/agentcore/council.py     3× invented API replaced; failure reporting works
pipeline/agent/brain.py           raises the real provider error
pipeline/agent/llm.py             Gemini thinking-budget fix (v5.9.2)
pipeline/workers/runner.py        VERSION 5.9.3 + orphaned-job reaper
pipeline/tests/                   80 tests incl. 3 guarding invented APIs
web/app/globals.css               typography pass (v5.9.2)
```

## After deploying

Filter Agent workspace to **Writer**. You now get one of two things, and both are
progress:

1. A script — the pipeline moves to render.
2. A line naming each provider and its exact failure — send it to me and I fix
   the specific thing rather than guessing.
