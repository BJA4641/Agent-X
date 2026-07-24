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
# v5.11.14: 60s is fine for the tick itself, but it spawned a killswitch check
# EVERY time (1,201/day). The check now runs on a slower multiple.
import datetime as _dt          # v5.11.17: was imported LOCALLY in some functions
                              # only, so tick() raised "name '_dt' is not defined"
                              # and the ENTIRE format mix silently never ran.
import os as _os_early
TICK_SECONDS = int(_os_early.environ.get("TICK_SECONDS", "60"))
KILLSWITCH_EVERY_N_TICKS = int(_os_early.environ.get("KILLSWITCH_EVERY_N_TICKS", "5"))
# v5.9.5: at most one ideation per account per window (DEC-021)
import os as _os
IDEATE_COOLDOWN_S = int(_os.environ.get("IDEATE_COOLDOWN_S", "1800"))
# v5.9.6: an item older than this no longer counts as "in flight" for the
# demand governor (REQ-GOV-2). Must exceed STALE_IDEA_HOURS so the sweep gets
# first attempt at rescuing it.
INFLIGHT_MAX_AGE_H = int(_os.environ.get("INFLIGHT_MAX_AGE_H", "6"))
# v5.10.7 REQ-BACKPRESSURE-1: an unapproved draft has produced ZERO business
# value and has already cost money. Producing a twelfth draft while eleven wait
# on a human is spend with no possible return. Production pauses until the queue
# drains below this depth.
MAX_AWAITING_APPROVAL = int(_os.environ.get("MAX_AWAITING_APPROVAL", "5"))

# v5.11.11 REQ-CONTENT-MIX — a real account does not post one format.
#
# Observed 2026-07-24: three reels for @puppy.parent, zero for @glowup.daily,
# zero carousels and zero stories — because ideation only ever spawned the reel
# path. A working brand day is a MIX, and the cheap formats carry the volume:
# a carousel is ~$0.015 and a story ~$0.003, against ~$0.02-0.10 for a reel.
#
# Format -> how many per account per day. Env-tunable; set any to 0 to disable.
DAILY_FORMAT_MIX = {
    "reel":     int(_os.environ.get("MIX_REEL", "1")),
    "carousel": int(_os.environ.get("MIX_CAROUSEL", "1")),
    "story":    int(_os.environ.get("MIX_STORY", "5")),
}
FORMAT_JOB = {
    "reel": "editorial.plan_one",
    "carousel": "editorial.plan_carousel",
    "story": "editorial.plan_story",
}


def formats_needed(sb, account_id, mix: dict = None, produced: dict = None) -> dict:
    """How many of each format this account still owes TODAY.

    Pure enough to test: pass `produced` to skip the DB entirely.
    """
    mix = mix or DAILY_FORMAT_MIX
    if produced is None:
        produced = produced_by_format_today(sb, account_id)
    need = {}
    for fmt, target in mix.items():
        got = int(produced.get(fmt) or 0)
        if target > got:
            need[fmt] = target - got
    return need


def produced_by_format_today(sb, account_id) -> dict:
    """Count board items created today per format for this account."""
    out = {}
    if sb is None:
        return out
    try:
        import datetime as _dt2
        start = _dt2.datetime.utcnow().replace(hour=0, minute=0, second=0,
                                               microsecond=0).isoformat() + "Z"
        rows = (sb.table("board_items").select("payload,topic")
                .eq("account_id", str(account_id))
                .gte("created_at", start).limit(300).execute().data) or []
        for r in rows:
            fmt = ((r.get("payload") or {}).get("format")
                   or ("carousel" if str(r.get("topic", "")).startswith("[carousel]") else
                       "story" if str(r.get("topic", "")).startswith("[story]") else "reel"))
            out[fmt] = int(out.get(fmt) or 0) + 1
    except Exception:
        pass
    return out


def awaiting_approval(sb, account_id=None) -> int:
    """Drafts sitting in the founder's approval queue."""
    if sb is None:
        return 0
    try:
        q = sb.table("board_items").select("id", count="exact").eq("status", "drafted")
        if account_id:
            q = q.eq("account_id", str(account_id))
        return int(q.execute().count or 0)
    except Exception:
        return 0


def _produced_today(sb, account_id) -> int:
    """Items that reached approved/scheduled/published today for this account.
    'prep' items are excluded (DEC-025)."""
    if sb is None:
        return 0
    try:
        import datetime as _dt
        start = _dt.datetime.combine(_dt.date.today(), _dt.time.min).isoformat() + "Z"
        res = (sb.table("board_items").select("id", count="exact")
               .in_("status", ["approved", "scheduled", "published"])
               .eq("account_id", str(account_id))
               .gte("created_at", start).execute())
        return int(res.count or 0)
    except Exception:
        return 0


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

    # v5.7 SOFT PAUSE: no NEW content work; in-flight jobs already queued keep
    # processing. Ops chains (heartbeat/snapshot/desk) are unaffected.
    from agentcore import soft_pause_on as _soft
    if _soft():
        bus.agent("ceo", "⏸ soft pause — finishing in-flight work, taking no new work",
                  "info", "tick_soft_paused", job_id=job.id)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "soft_paused": True})
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

    # v5.8 BATCH4: loop over ALL active accounts (the old single-account
    # mandate is retired — glowup + puppy both get daily content now).
    accounts = active_accounts(sb) or []
    if not accounts:
        bus.agent("ceo", "no active accounts — idling (resume one in project_accounts)",
                  "info", "tick_idle", job_id=job.id)
        _schedule_next_tick(w, job)
        w.queue.complete(job, {"ok": True, "no_accounts": True})
        return

    from ..common import is_account_active
    touched = []
    for acct in accounts:
        if not is_account_active(sb, acct["id"]):
            continue
        bus.agent("ceo", f"👔 tick — account: {acct.get('name','?')} (@{acct.get('handle','?')})",
                  "info", "tick_account", job_id=job.id, account_id=acct["id"])

        _sweep_stale_ideas(w, bus, sb, acct, job)
        inflight = _count_inflight(sb, acct["id"])
        target = int(acct.get("posts_per_day") or POSTS_PER_DAY_DEFAULT)
        bus.agent("coo", f"in-flight for @{acct.get('handle','?')}: {inflight}/{MAX_INFLIGHT_PER_ACCOUNT}, daily target {target}",
                  "info", "inflight", job_id=job.id)

        # No brand bible yet → generate it first, skip content this tick.
        if not acct.get("brand_bible"):
            bus.agent("architect", f"🏛️ no brand bible for {acct.get('name','?')} — queuing generation",
                      "info", "brand_queued", job_id=job.id)
            job_of(w, "brand_studio.generate", {"niche": acct.get("niche", "")},
                   parent=job, account_id=acct["id"], project_id=acct.get("project_id"),
                   priority=Priority.HIGH)
            touched.append(acct.get("handle"))
            continue

        # v5.9.5 DEMAND GOVERNOR (DEC-021). The old rule spawned an ideate
        # whenever inflight < cap — with cleared/failed items constantly
        # freeing slots this produced ~1,000 ideations/day and 7,404 cleared
        # board items in 7 days ($12 of pure churn). New rule: ideate ONLY
        # when today's quota still has unmet demand, and at most once per
        # IDEATE_COOLDOWN_S window (windowed idempotency key makes floods
        # structurally impossible regardless of tick cadence).
        produced = _produced_today(sb, acct["id"])
        waiting = awaiting_approval(sb, acct["id"])
        if waiting >= MAX_AWAITING_APPROVAL:
            bus.agent("coo", f"🧺 @{acct.get('handle','?')} has {waiting} draft(s) awaiting your "
                             f"approval (cap {MAX_AWAITING_APPROVAL}) — pausing new production until "
                             f"the queue drains. Nothing is lost; the drafts are ready when you are.",
                      "warn", "backpressure", job_id=job.id, account_id=acct["id"])
            touched.append(acct.get("handle"))
            continue
        # v5.11.11 REQ-CONTENT-MIX: fill the cheap formats first. Stories and
        # carousels do not touch ffmpeg, so they keep an account posting daily
        # even while a reel is queued behind the heavy lane.
        try:
            owed = formats_needed(sb, acct["id"])
            for fmt, count in owed.items():
                if fmt == "reel":
                    continue                      # the reel path is handled below
                jt = FORMAT_JOB.get(fmt)
                if not jt:
                    continue
                for k in range(min(count, 5)):
                    job_of(w, jt, {"account_id": acct["id"]},
                           parent=job, account_id=acct["id"],
                           project_id=acct.get("project_id"),
                           priority=Priority.NORMAL,
                           idempotency_key=f"mix:{acct['id']}:{fmt}:{k}:{_dt.date.today()}")
            if owed:
                bus.agent("coo", f"🎛️ format mix for @{acct.get('handle','?')}: "
                                 + ", ".join(f"{v}x {k}" for k, v in owed.items()),
                          "info", "format_mix", job_id=job.id, account_id=acct["id"])
        except Exception as e:
            bus.agent("coo", f"format mix skipped: {str(e)[:90]}", "warn",
                      "format_mix_err", job_id=job.id)

        need = max(0, target - produced - inflight)
        if need > 0 and inflight < MAX_INFLIGHT_PER_ACCOUNT:
            bucket = int(time.time() // IDEATE_COOLDOWN_S)
            job_of(w, "editorial.ideate", {
                "account_id": acct["id"], "project_id": acct.get("project_id"),
                "target_posts": min(need, MAX_INFLIGHT_PER_ACCOUNT - inflight),
            }, parent=job, account_id=acct["id"], project_id=acct.get("project_id"),
               priority=Priority.HIGH,
               idempotency_key=f"ideate:{acct['id']}:{bucket}")
        elif need <= 0:
            bus.agent("coo", f"@{acct.get('handle','?')} quota met for today "
                             f"({produced} produced + {inflight} in-flight ≥ {target}) — no ideation",
                      "info", "tick_quota_met", job_id=job.id)
        else:
            bus.agent("coo", f"@{acct.get('handle','?')} in-flight at cap — no new reels this tick",
                      "info", "tick_cap", job_id=job.id)

        # v5.8 CAROUSEL CADENCE: carousels_per_week from account config (default 3),
        # mapped to fixed weekdays so the schedule is predictable and idempotent.
        _maybe_spawn_carousel(w, job, sb, bus, acct)
        touched.append(acct.get("handle"))

    # CFO daily report every ~4 hours
    if int(time.time()) % (4*3600) < TICK_SECONDS:
        job_of(w, "cfo.daily_report", {}, parent=job, priority=Priority.LOW)
    # v5.11.14 REQ-CHAIN-1: this fired on EVERY tick — 1,201 runs/day to read one
    # boolean. The kill switch is a safety net, not a hot path.
    _tick_n = int(time.time() // max(TICK_SECONDS, 1))
    if _tick_n % max(KILLSWITCH_EVERY_N_TICKS, 1) == 0:
        job_of(w, "cfo.killswitch_check", {}, parent=job, priority=Priority.LOW)

    _schedule_next_tick(w, job)
    w.queue.complete(job, {"ok": True, "accounts": touched})


_CAROUSEL_DAYS = {1: {2}, 2: {1, 4}, 3: {0, 2, 4}, 4: {0, 1, 3, 4},
                  5: {0, 1, 2, 3, 4}, 6: {0, 1, 2, 3, 4, 5}, 7: {0, 1, 2, 3, 4, 5, 6}}

def _maybe_spawn_carousel(w, job, sb, bus, acct):
    """Spawn one editorial.plan_carousel on scheduled weekdays, once per day
    per account (idempotency key carries the date)."""
    try:
        cfg = acct.get("config") or {}
        cw = int(cfg.get("carousels_per_week", 3) or 0)
        if cw <= 0:
            return
        today = time.gmtime()
        if today.tm_wday not in _CAROUSEL_DAYS.get(min(cw, 7), set()):
            return
        datekey = time.strftime("%Y%m%d", today)
        j = Job(job_type="editorial.plan_carousel",
                payload={"account_id": acct["id"], "project_id": acct.get("project_id")},
                # v5.11.17: Priority.MEDIUM has never existed. Every carousel
                # spawn raised AttributeError and was swallowed by the guard —
                # which is why zero carousels were ever produced.
                priority=Priority.NORMAL, account_id=acct["id"],
                project_id=acct.get("project_id"),
                idempotency_key=f"carousel:{acct['id']}:{datekey}")
        w.queue.enqueue(j)
        bus.agent("coo", f"🖼️ carousel day for @{acct.get('handle','?')} — planning one",
                  "info", "carousel_spawn", job_id=job.id, account_id=acct["id"])
    except Exception as e:
        bus.agent("coo", f"carousel spawn skipped: {str(e)[:80]}", "warn",
                  "carousel_skip", job_id=job.id)


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
        # v5.8.7 TRIP = DEGRADE, NOT STOP.
        # Old behaviour flipped the hard kill switch: the worker went silent and
        # stayed silent until a human noticed. The money problem is PAID spend —
        # so suspend paid calls and let the free council keep producing. Only if
        # money is still leaking while already in free_only (which should be
        # impossible, free = $0) do we hard-stop.
        from agentcore import config as _cfg
        from agentcore import costmode as _cm
        if _cm.free_only():
            sb.table("settings").upsert({
                "tenant_id": _cfg.TENANT_ID, "key": "kill_switch",
                "value": {"on": True, "by": "no_output_guard",
                          "reason": f"${spend:.2f} spent since boot with zero output "
                                    f"WHILE already in free_only — real fault, hard stop"},
            }, on_conflict="tenant_id,key").execute()
            bus.agent("ceo", f"🛑 HARD STOP: ${spend:.2f} spent with zero output even in "
                              f"free-only mode. Something is charging us outside the router. "
                              f"Kill switch on — needs a human.",
                      "critical", "auto_killswitch", job_id=job.id)
            return True
        _cm.degrade(f"${spend:.2f} spent since boot with zero output", by="no_output_guard")
        bus.agent("ceo", f"💚 PAID SPEND SUSPENDED: ${spend:.2f} since boot with ZERO items "
                          f"reaching approved/published. Switched to FREE-ONLY mode — the "
                          f"worker keeps writing and grading on free models at $0 while you "
                          f"look at the failing step. Paid access returns automatically at "
                          f"the next budget day, or hit Resume paid in Studio.",
                  "warn", "auto_free_only", job_id=job.id)
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
        # v5.9.1 DEADLOCK FIX. This counted the WHOLE board but compared the
        # result against MAX_INFLIGHT_PER_ACCOUNT (a per-account limit). Four
        # stale ideas therefore blocked every account forever:
        #     "in-flight for @glowup.daily: 4/2 — no new reels this tick"
        # board_items does have account_id in this deployment, so scope it.
        # v5.9.6 REQ-GOV-2 (DEC-035): only count items that are plausibly still
        # MOVING. The governor computes need = quota - produced - inflight; a
        # permanently stalled item therefore suppressed ideation forever
        # ("quota met (0 produced + 2 in-flight >= 1) — no ideation") while the
        # account published nothing. Items older than INFLIGHT_MAX_AGE_H no
        # longer count as demand-satisfying; the stale sweep still owns cleanup.
        import datetime as _dt
        floor_iso = (_dt.datetime.utcnow()
                     - _dt.timedelta(hours=INFLIGHT_MAX_AGE_H)).isoformat() + "Z"
        q = (sb.table("board_items").select("id", count="exact")
             .in_("status", ["idea", "drafted", "approved", "scheduled"]))
        try:
            q = q.gte("created_at", floor_iso)
        except Exception:
            pass   # client without gte -> fall back to un-aged count, never to 0
        if account_id:
            try:
                res = q.eq("account_id", str(account_id)).execute()
                return int(res.count or 0)
            except Exception:
                pass          # legacy rows without account_id -> global fallback
        return int(q.execute().count or 0)
    except Exception:
        return 0


STALE_IDEA_HOURS = 2

def _sweep_stale_ideas(w, bus, sb, acct, job):
    """v5.9.1 — un-stick the board.

    An `idea` is created by editorial.ideate, which immediately enqueues
    editorial.plan_one to draft it. If that chain dies (crash, circuit breaker,
    kill switch mid-flight) the idea sits at `idea` forever, counts against the
    in-flight cap, and the account is blocked permanently — no error, no event,
    just silence. Four such ideas from 12:03 held both live accounts all day.

    Any idea older than STALE_IDEA_HOURS gets ONE re-planning attempt; if it has
    already been retried, it is cleared so it stops occupying a slot."""
    if sb is None:
        return
    try:
        import datetime as _dt
        cutoff = (_dt.datetime.utcnow() - _dt.timedelta(hours=STALE_IDEA_HOURS)).isoformat() + "Z"
        rows = (sb.table("board_items").select("id,topic,payload,created_at")
                .eq("status", "idea").eq("account_id", str(acct["id"]))
                .lt("created_at", cutoff).limit(10).execute().data) or []
    except Exception:
        return
    for r in rows:
        payload = dict(r.get("payload") or {})
        # v5.9.5 ROOT-CAUSE FIX: the topic lives in the board `topic` COLUMN
        # (board_add puts it there) — the old payload-only read came back
        # empty for every normal idea, so every re-plan fired
        # editorial.plan_one with topic="" → creative.write_script "no topic"
        # fatal (9 in 7 days). Read the column first.
        topic = (r.get("topic") or payload.get("topic") or payload.get("title") or "")
        # v5.9.5: an EMPTY topic can never be planned — re-queueing it just
        # manufactures a "creative.write_script: no topic" fatal (9 in the
        # last 7 days). Clear it immediately with the reason recorded.
        if not topic.strip():
            payload["cleared_reason"] = "empty_topic"
            try:
                sb.table("board_items").update(
                    {"status": "cleared", "payload": payload}).eq("id", r["id"]).execute()
            except Exception:
                pass
            bus.agent("coo", "🧹 cleared stale idea with EMPTY topic (unplannable)",
                      "warn", "idea_cleared", job_id=job.id, item_id=r["id"])
            continue
        if payload.get("replan_attempted"):
            try:
                sb.table("board_items").update({"status": "cleared"}).eq("id", r["id"]).execute()
            except Exception:
                pass
            bus.agent("coo", f"🧹 cleared stale idea after a failed re-plan — \"{topic[:60]}\" "
                             f"(it was holding an in-flight slot)",
                      "warn", "idea_cleared", job_id=job.id, item_id=r["id"])
            continue
        payload["replan_attempted"] = True
        try:
            sb.table("board_items").update({"payload": payload}).eq("id", r["id"]).execute()
        except Exception:
            pass
        # v5.9.6 REQ-DEDUPE-1: the re-plan path was the one spawn site without an
        # idempotency key, so every sweep queued ANOTHER write_script for the same
        # item — "Black Spots Gone Instantly!" was queued 5x. Harmless while the
        # writer was dead; a 5x spend multiplier the moment escalation lands.
        job_of(w, "editorial.plan_one",
               {"item_id": r["id"], "topic": topic, "bucket": payload.get("bucket", "trend")},
               parent=job, account_id=acct["id"], project_id=acct.get("project_id"),
               priority=Priority.HIGH,
               idempotency_key=f"replan:{r['id']}")
        bus.agent("coo", f"♻️ re-planning stale idea (>{STALE_IDEA_HOURS}h at 'idea') — \"{topic[:60]}\"",
                  "info", "idea_replan", job_id=job.id, item_id=r["id"])
