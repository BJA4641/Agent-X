"""departments/portfolio.py — A (Portfolio Management) + tick loop.

The CEO/COO tick job runs once per minute (configurable). It:
  1. Checks kill switch + budget (CFO).
  2. Picks the single active account (per user mandate).
  3. Checks how many items that account already has in-flight.
  4. If under post cadence, spawns discovery+ideation into Editorial.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, Priority, FatalError
from ..common import (active_accounts, first_active_account, board_get,
                      hard_budget_ok, kill_switch, job_of)

# Cap to prevent runaway parallel production per tick.
MAX_INFLIGHT_PER_ACCOUNT = 2
POSTS_PER_DAY_DEFAULT = 2
TICK_SECONDS = 60


def register(w: Worker):
    w.register("portfolio.tick", tick)
    w.register("portfolio.boot", boot)


def boot(w: Worker, job: Job, ctx: AgentContext):
    """Kicks off background loop jobs (scout refresh, daily report schedule)."""
    bus = ctx.deps["bus"]
    bus.agent("ceo", "👔 Agent-X v5 portfolio boot — wiring blueprints", "success",
              "boot", job_id=job.id)
    # Seed a scout.run immediately and then a recurring tick every TICK_SECONDS
    job_of(w, "research.scout_run", {"reason": "boot"}, parent=job,
           priority=Priority.HIGH)
    # First content tick in 20s (after scout warms cache)
    job_of(w, "portfolio.tick", {"boot": True}, parent=job,
           priority=Priority.NORMAL)
    w.queue.complete(job, {"ok": True})


def tick(w: Worker, job: Job, ctx: AgentContext):
    """One portfolio decision tick. Idempotent."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()

    if kill_switch():
        bus.agent("ceo", "⏸ kill switch on — tick is a no-op", "warn",
                  "tick_paused", job_id=job.id)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "paused": True})
        return

    if not hard_budget_ok():
        bus.agent("cfo", "⛔ daily budget exhausted — no new content this tick",
                  "warn", "tick_budget", job_id=job.id)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "budget_blocked": True})
        return

    acct = first_active_account(sb)
    if not acct:
        bus.agent("ceo", "no active accounts — idling (resume one in project_accounts)",
                  "info", "tick_idle", job_id=job.id)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "no_accounts": True})
        return

    bus.agent("ceo", f"👔 tick — active account: {acct.get('name','?')} (@{acct.get('handle','?')})",
              "info", "tick_account", job_id=job.id, account_id=acct["id"])

    # Count in-flight items (idea/drafted/approved/scheduled) for this account
    inflight = _count_inflight(sb, acct["id"])
    target = int(acct.get("posts_per_day") or POSTS_PER_DAY_DEFAULT)
    bus.agent("coo", f"in-flight for @{acct.get('handle','?')}: {inflight}/{MAX_INFLIGHT_PER_ACCOUNT}, daily target {target}",
              "info", "inflight", job_id=job.id)

    if inflight < MAX_INFLIGHT_PER_ACCOUNT:
        # Spawn ideation -> Editorial pipeline for this account
        job_of(w, "editorial.ideate", {
            "account_id": acct["id"], "project_id": acct.get("project_id"),
            "target_posts": max(1, MAX_INFLIGHT_PER_ACCOUNT - inflight),
        }, parent=job, account_id=acct["id"], project_id=acct.get("project_id"),
           priority=Priority.HIGH)
    else:
        bus.agent("coo", "in-flight at cap — not starting new work this tick",
                  "info", "tick_cap", job_id=job.id)

    # CFO daily report every ~4 hours
    if int(time.time()) % (4*3600) < TICK_SECONDS:
        job_of(w, "cfo.daily_report", {}, parent=job, priority=Priority.LOW)
    # Kill-switch heartbeat
    job_of(w, "cfo.killswitch_check", {}, parent=job, priority=Priority.LOW)

    _schedule_next_tick(w, job)
    w.queue.complete(job, {"ok": True, "active_account": acct.get("name"),
                           "inflight": inflight})


def _schedule_next_tick(w: Worker, job: Job):
    """Enqueue the next portfolio.tick so the system self-schedules even if
    the Railway process restarts (no persistent while-loop in memory)."""
    j = Job(job_type="portfolio.tick", payload={"scheduled": True},
            priority=Priority.LOW,
            scheduled_for=time.time() + TICK_SECONDS,
            idempotency_key=f"tick:{int(time.time()//TICK_SECONDS)}")
    w.queue.enqueue(j)


def _count_inflight(sb, account_id) -> int:
    if sb is None:
        return 0
    try:
        from ..common import board_get
        res = (sb.table("board_items")
               .select("id", count="exact")
               .eq("status", "idea")
               .or_("status.eq.drafted,status.eq.approved,status.eq.scheduled")
               .execute())
        # Can't easily filter by account_id because legacy board_items don't
        # have account_id columns in all deployments; count globally and cap
        # conservatively.
        return int(res.count or 0)
    except Exception:
        return 0
