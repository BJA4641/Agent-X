# Agent-X v5.9.0 — THE EVENT FEED HAS NEVER WORKED

Supersedes v5.8.9 (contains it). `73 passed` · `npm run build` clean.

---

## The finding

Every event from every v5 department — ceo, coo, cfo, cqo, cto — has been
**silently discarded since the department architecture shipped.** Verified
against production:

```sql
select count(*) from agent_events
where agent in ('ceo','coo','cfo','cqo','cto') or emitter in (...);
-- 0
```

Zero. Not one.

**Cause:** `agent_events.id` is `GENERATED ALWAYS AS IDENTITY`. Postgres rejects
any explicit value for such a column (SQLSTATE 428C9). The persister sent
`"id": event.id` — a 12-char hex string — on every single event. The insert threw,
and the handler caught it and printed one line:

```python
except Exception as e:
    print(f"[events.persist] insert failed (non-fatal): {e}")
```

A 100% failure rate looked like a quiet log line.

Two further mismatches, fixed at the same time:
- the table and the dashboard key off **`agent`**; we only wrote `emitter`
- the feed sums **`cost_usd`**; we only wrote `cost_cents`

**What this explains:** the dead Agent workspace, the missing agents, and — most
importantly — *why you could not see why the pipeline was idle*. Every diagnostic
the departments emitted ("kill switch on", "daily budget exhausted", "no active
accounts") was thrown away before it reached you. You were flying blind, and so
was I until the constraint check.

Persist failures are now loud in the Railway log and recorded to
`settings.event_persist_error` so the dashboard can surface them.

---

## Your accounts are NOT all paused

The UI label is misleading. `STATUS_LABELS` maps **`needs_setup` → "queued"** —
so "queued" means *setup was never finished*, not *waiting in line*.

Actual state:

```
100  paused         (status=paused, paused=true)
  3  needs_setup    -> shown as "queued"
  1  strategizing   cat.facts
  1  ready          glowup.daily
```

The worker does **not** look at `status` at all. `is_account_active()` checks two
booleans: `account.paused` and `project.paused`. By that rule **two accounts are
already live**:

| account | project | account.paused | project.paused |
|---|---|---|---|
| `glowup.daily` | Skincare Portfolio | false | false |
| `puppy.parent` | Pets Portfolio | false | false |

So there is nothing for you to resume — the gate is elsewhere.

---

## The likely gate: budget, read from the wrong place

`hard_budget_ok()` reads `DAILY_BUDGET_USD` from the **worker env**, not from
`settings.daily_budget`. Your DB says **$2.50**; spend today is **$1.136**; your
wallet card shows **$1.00**. If Railway's `DAILY_BUDGET_USD` is `1.00`, every
tick hits:

```python
if not hard_budget_ok():
    bus.agent("cfo", "⛔ daily budget exhausted — no new content this tick")
    return
```

…and returns before it ever looks at an account — while the event explaining it
was dropped by the bug above. That fits the evidence exactly: `portfolio.tick`
ran 118 times in two hours, all `done`, and produced nothing.

v5.9.0 publishes the **effective** value to `settings.provider_inventory`:

```json
"effective_config": { "daily_budget_usd": 1.0, "env_daily_budget_raw": "1.00", "tenant_id": "me" }
```

After deploying, read that. If it says 1.0, raise `DAILY_BUDGET_USD` in Railway
to 2.50 and the tick will proceed. **Check this before changing anything else.**

---

## Also in this release (from v5.8.9)

- **Hotfix:** `providers.probe`, `strategy.audit`, `strategy.arena_scout` all
  crashed with `TypeError: takes 2 positional arguments but 3 were given`.
  Handlers are `(w, job, ctx)`. Fixed, plus an arity test across every registered
  handler in every department.
- **Sticky header + sidebar.** `.wrap.shell` became a grid; grid items stretch to
  row height so `position: sticky` had nothing to stick to. Fixed with
  `align-self: start` and their own scroll boxes.
- **Full agent roster** in the workspace, idle agents dimmed and labelled.
- **PipelineBlocker** banner when no account is eligible.

## Files (11)

```
pipeline/agentcore/events.py                THE FIX — persister contract
pipeline/workers/runner.py                  VERSION 5.9.0 + effective_config
pipeline/workers/departments/providers.py   handler arity
pipeline/workers/departments/strategy.py    handler arity
pipeline/tests/test_v590_event_persist.py   NEW — 5 tests
pipeline/tests/test_v589_handler_arity.py   NEW — arity guard
web/app/globals.css                         sticky chrome
web/app/dashboard/workspace/page.tsx        full roster
web/components/PipelineBlocker.tsx          NEW
web/app/api/projects/accounts-summary/route.ts  NEW
web/app/api/version/route.ts                WEB_VERSION 5.9.0
```

## After deploying — in this order

1. Banner green at **web v5.9.0 · worker v5.9.0**.
2. Open Agent workspace. You should now see **ceo / coo / cfo / cqo** chatter for
   the first time. Whatever it says is your real blocker.
3. Read `settings.provider_inventory → effective_config.daily_budget_usd`.
   If it is below your spend, raise `DAILY_BUDGET_USD` in Railway.
4. Only then worry about resuming accounts.
