# Agent-X v5.8.9 — HOTFIX + STICKY CHROME + FULL AGENT ROSTER

**Deploy this one.** v5.8.8 shipped a runtime bug that killed all three of my new
jobs. `68 passed` pytest · `npm run build` clean.

---

## 1. HOTFIX — my v5.8.8 jobs all crashed

```
providers.probe       TypeError: probe() takes 2 positional arguments but 3 were given
strategy.arena_scout  TypeError: arena_scout() takes 2 positional arguments but 3 were given
strategy.audit        TypeError: audit() takes 2 positional arguments but 3 were given
```

My mistake. Every department handler is called as `(w, job, ctx)` and I wrote
them as `(w, job)`. `py_compile` and `npm run build` cannot catch this — it only
appears when the worker dispatches. That is why the AI models page still says
"No probe has run yet".

Fixed, plus a regression test (`test_v589_handler_arity.py`) that walks **every
handler registered by every department** and asserts 3 positional args. This
class of bug cannot ship again.

---

## 2. Why only 2 agents show in Agent workspace

Not a bug in the roster — a stalled pipeline. Historical event counts:

```
visuals   946   last seen Jul 19      scout    590   last seen TODAY
brain     871   last seen Jul 19      grader   429   last seen TODAY
composer  726   last seen Jul 19      voice    404   last seen Jul 19
strategy  230   ...                   qa       143   ...
```

All 16 agents exist and have worked before. The chip row was built from
`new Set(last 200 events)`, so when only Scout is active you see one or two chips
and it looks like the rest were never built.

**The actual blocker: zero accounts are `active`.**

```
paused 100 · needs_setup 3 · strategizing 1 · ready 1 · ACTIVE 0
```

Scout is the only account-independent agent — it scouts trends globally. Writer,
Visuals, Voice, Editor, Publisher all need an **active** account to have a job.
With everything paused they stay registered and idle. That is also why the board
sits at 4 `idea` items and nothing drafts.

Two changes:
- The chip row now shows the **full roster**, with un-heard-from agents dimmed
  and labelled `idle` (hover explains why).
- A `PipelineBlocker` banner appears on the workspace whenever `active === 0`,
  states the cause plainly and links to the account page.

**Nothing in this release starts production. You have to resume one account.**

---

## 3. Sticky header + sidebar

`.sidebar` had `position: sticky` but `.wrap.shell` became a CSS **grid**, and
grid items stretch to row height — so there was nothing to stick against. Fixed
with `align-self: start` plus their own scroll box, and the header is now a real
sticky bar with a blur backdrop. Both un-stick below 1100px where the rail wraps.

---

## Files (9)

```
pipeline/workers/departments/providers.py   handler signature + ctx.deps bus
pipeline/workers/departments/strategy.py    handler signature + ctx.deps bus
pipeline/workers/runner.py                  VERSION 5.8.9
pipeline/tests/test_v589_handler_arity.py   NEW — arity guard over all departments
web/app/globals.css                         sticky header / sidebar / right rail
web/app/dashboard/workspace/page.tsx        full roster + idle markers + blocker
web/components/PipelineBlocker.tsx          NEW — "no account is active" advisory
web/app/api/projects/accounts-summary/route.ts  NEW — counts only
web/app/api/version/route.ts                WEB_VERSION 5.8.9
```

## After deploying

1. Banner should read **web v5.8.9 · worker v5.8.9** in green.
2. Within ~2 min the AI models panel fills with real provider status and balances.
3. Arena scout writes `settings.arena_rankings` and rebuilds the free council roster.
4. Then — **resume ONE account** and watch the other agents wake up.
