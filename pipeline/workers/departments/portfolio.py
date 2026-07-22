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

    # v5.6 NO-OUTPUT KILL SWITCH: if we have spent real money since this worker
    # booted and NOTHING has reached approved/scheduled/published, the pipeline
    # is broken — stop spending automatically instead of burning for 63 hours.
    if _no_output_trip(bus, sb, job):
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "auto_killed": True})
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

    # BUG FIX v5.3: double-check the account is actually active (not paused,
    # project not paused). first_active_account should already filter, but be safe.
    from ..common import is_account_active
    if not is_account_active(sb, acct["id"]):
        bus.agent("ceo", f"account {acct.get('name','?')} is paused (or project paused) — skipping",
                  "info", "tick_paused", job_id=job.id)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "paused": True})
        return

    bus.agent("ceo", f"👔 tick — active account: {acct.get('name','?')} (@{acct.get('handle','?')})",
              "info", "tick_account", job_id=job.id, account_id=acct["id"])

    # Count in-flight items (idea/drafted/approved/scheduled) for this account
    inflight = _count_inflight(sb, acct["id"])
    target = int(acct.get("posts_per_day") or POSTS_PER_DAY_DEFAULT)
    bus.agent("coo", f"in-flight for @{acct.get('handle','?')}: {inflight}/{MAX_INFLIGHT_PER_ACCOUNT}, daily target {target}",
              "info", "inflight", job_id=job.id)

    # Phase 3: if this account lacks a brand bible, generate one FIRST before producing.
    if not acct.get("brand_bible"):
        bus.agent("architect", f"🏛️ no brand bible for {acct.get('name','?')} — queuing generation",
                  "info", "brand_queued", job_id=job.id)
        from ..common import job_of as _jof
        _jof(w, "brand_studio.generate", {
            "niche": acct.get("niche", ""),
        }, parent=job, account_id=acct["id"], project_id=acct.get("project_id"),
           priority=Priority.HIGH)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "active_account": acct.get("name"),
                               "inflight": inflight, "generating_brand_bible": True})
        return

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


_BOOT_TS = time.time()
_NO_OUTPUT_SPEND_USD = 0.50   # spend this much since boot with zero output -> stop
_NO_OUTPUT_GRACE_S = 900      # give a fresh boot 15 min before judging

def _no_output_trip(bus, sb, job) -> bool:
    """Auto kill switch: spend > $0.50 since boot AND zero items have reached
    approved/scheduled/published since boot AND boot was >15 min ago."""
    if sb is None or (time.time() - _BOOT_TS) < _NO_OUTPUT_GRACE_S:
        return False
    try:
        import datetime as _dt
        boot_iso = _dt.datetime.utcfromtimestamp(_BOOT_TS).isoformat() + "Z"
        led = sb.table("run_ledger").select("cost_usd").gte("created_at", boot_iso).execute()
        spend = sum(float(x.get("cost_usd") or 0) for x in (led.data or []))
        if spend <= _NO_OUTPUT_SPEND_USD:
            return False
        out = (sb.table("board_items").select("id", count="exact")
               .in_("status", ["approved", "scheduled", "published"])
               .gte("created_at", boot_iso).execute())
        if int(out.count or 0) > 0:
            return False
        # TRIP: flip the kill switch, scream, leave a recommendation.
        from agentcore import config as _cfg
        sb.table("settings").upsert({
            "tenant_id": _cfg.TENANT_ID, "key": "kill_switch",
            "value": {"on": True, "by": "no_output_guard",
                       "reason": f"${spend:.2f} spent since boot with zero output"},
        }, on_conflict="tenant_id,key").execute()
        bus.agent("ceo", f"🛑 AUTO KILL SWITCH: ${spend:.2f} spent since boot with ZERO items "
                          f"reaching approved/published. Pipeline is broken — spending stopped. "
                          f"Fix the failing step, then turn the kill switch off in Settings.",
                  "critical", "auto_killswitch", job_id=job.id)
        try:
            import datetime as _dt2
            sb.table("ceo_recommendations").insert({
                "severity": "critical", "category": "pause",
                "recommendation": "🛑 Auto kill switch engaged — money out, nothing published",
                "reasoning": f"${spend:.2f} spent since worker boot with zero items reaching "
                             f"approved/scheduled/published. A pipeline step is failing repeatedly. "
                             f"Check the activity feed for the failing job type, deploy the fix, "
                             f"then disable the kill switch in Settings.",
                "projected_roi": 0.0, "projected_value_usd": spend,
                "action_url": "/dashboard/settings",
                "day": _dt2.date.today().isoformat(),
            }).execute()
        except Exception:
            pass
        return True
    except Exception:
        return False


def _count_inflight(sb, account_id) -> int:
    if sb is None:
        return 0
    try:
        from ..common import board_get
        # v5.6 P0 FIX: the old chain .eq("status","idea").or_("status.eq.drafted,...")
        # combined as AND in supabase-py -> matched ZERO rows -> the in-flight cap
        # NEVER engaged -> ideation flooded 7,307 items. in_() is the correct filter.
        res = (sb.table("board_items")
               .select("id", count="exact")
               .in_("status", ["idea", "drafted", "approved", "scheduled"])
               .execute())
        # Can't easily filter by account_id because legacy board_items don't
        # have account_id columns in all deployments; count globally and cap
        # conservatively.
        return int(res.count or 0)
    except Exception:
        return 0
