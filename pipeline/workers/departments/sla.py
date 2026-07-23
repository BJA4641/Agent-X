"""departments/sla.py — v5.9.5 Publishing SLA engine.

Two jobs:

  sla.plan_day  (daily, idempotent per UTC date)
      For every ACTIVE account, writes today's publishing plan into
      settings.sla_plan:{date} — quota (posts_per_day) and evenly spaced
      target deadlines across the publishing window.

  sla.monitor   (recurring, SLA_MONITOR_INTERVAL_S, default 300s)
      1. Classifies every active account:  on_track / at_risk / behind / breached
         using a simple minutes-per-post heuristic (DEC-022): a post still
         needing production is "at risk" when less than SLA_MINUTES_PER_POST
         of runway remains before its target deadline, "behind" when the
         deadline has passed, "breached" when the whole day's quota can no
         longer physically fit before midnight UTC.
      2. Writes the full classification to settings.sla_status so the web
         layer can render it.
      3. Self-prioritizes: queued jobs belonging to behind/breached accounts
         get a deadline stamped so fair_claim_order (agentcore.jobs) pulls
         them first.
      4. Breaches reach the founder desk via ceo_recommendations.
      5. Self-heal: any job stuck in_progress longer than
         SLA_STUCK_JOB_S (default 900s) is requeued (crash recovery without
         waiting for a container reboot).

No LLM calls anywhere in this module — pure DB math, $0.
"""
from __future__ import annotations
import os
import time
import datetime as _dt
from agentcore import Worker, Job, AgentContext, Priority
from ..common import active_accounts, job_of

SLA_MINUTES_PER_POST = int(os.environ.get("SLA_MINUTES_PER_POST", "45"))
SLA_MONITOR_INTERVAL_S = int(os.environ.get("SLA_MONITOR_INTERVAL_S", "300"))
SLA_STUCK_JOB_S = int(os.environ.get("SLA_STUCK_JOB_S", "900"))
# v5.9.6 REQ-SLA-TZ (DEC-031): the founder mandate is "every active account
# completes its full daily production pipeline before 14:00 Asia/Dubai,
# configurable per account". v5.9.5 shipped an 08:00-22:00 UTC window, which
# measured the wrong deadline entirely.
SLA_DEADLINE_LOCAL = os.environ.get("SLA_DEADLINE_LOCAL", "14:00")
SLA_TIMEZONE = os.environ.get("SLA_TIMEZONE", "Asia/Dubai")
SLA_WINDOW_START_H = int(os.environ.get("SLA_WINDOW_START_H", "6"))   # local start hour


def _tz(name: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return None


def resolve_deadline_utc(deadline_local: str = None, tzname: str = None,
                         day: "_dt.date" = None) -> float:
    """Resolve 'HH:MM' in `tzname` on `day` to a UTC epoch. Pure + testable.
    Falls back to a fixed UTC offset table if zoneinfo data is unavailable."""
    deadline_local = deadline_local or SLA_DEADLINE_LOCAL
    tzname = tzname or SLA_TIMEZONE
    day = day or _dt.date.today()
    hh, _, mm = deadline_local.partition(":")
    hh, mm = int(hh or 14), int(mm or 0)
    tz = _tz(tzname)
    if tz is not None:
        return _dt.datetime.combine(day, _dt.time(hh, mm), tzinfo=tz).timestamp()
    offsets = {"Asia/Dubai": 4, "Europe/Istanbul": 3, "Europe/London": 1, "UTC": 0}
    off = offsets.get(tzname, 0)
    naive = _dt.datetime.combine(day, _dt.time(hh, mm))
    return (naive - _dt.timedelta(hours=off)).replace(tzinfo=_dt.timezone.utc).timestamp()


def account_deadline_utc(acct: dict, day=None) -> float:
    """Per-account override: project_accounts.config.sla_deadline / sla_timezone."""
    cfg = (acct or {}).get("config") or {}
    return resolve_deadline_utc(cfg.get("sla_deadline"), cfg.get("sla_timezone"), day)

_TENANT = os.environ.get("TENANT_ID", "me")


# v5.9.7 REQ-SLASTAGE-1 (DEC-031) — back-planned stage budgets.
# A single end-of-day deadline is not actionable: by the time it breaches it is
# already too late. Each stage therefore carries its own deadline, derived by
# subtracting the remaining stages' budgets from the account's publish deadline.
# fair_claim_order (v5.9.5) already pulls deadline-urgent jobs first, so
# stamping these turns the existing fairness mechanism into SLA enforcement.
STAGE_BUDGETS_MIN = {
    "editorial.ideate":       5,
    "editorial.plan_one":     5,
    "editorial.plan_carousel": 5,
    "creative.write_script": 15,
    "creative.write_carousel": 15,
    "cqo.grade_script":      15,
    "creative.render":       30,
    "postprod.finish":       15,
    "monetization.inject":    5,
    "human_desk.sync":       20,
    "distribution.publish":  10,
}
# Order matters: everything AFTER a stage still has to fit before the deadline.
STAGE_ORDER = ["editorial.ideate", "editorial.plan_one", "creative.write_script",
               "cqo.grade_script", "creative.render", "postprod.finish",
               "monetization.inject", "distribution.publish"]


def stage_deadline(job_type: str, publish_deadline_utc: float) -> float:
    """Deadline for one stage = publish deadline minus every downstream budget.

    Pure function (unit-tested). Unknown job types return the publish deadline
    unchanged, which is correct-but-loose rather than wrong.
    """
    if job_type not in STAGE_ORDER:
        return publish_deadline_utc
    idx = STAGE_ORDER.index(job_type)
    downstream = sum(STAGE_BUDGETS_MIN.get(t, 0) for t in STAGE_ORDER[idx + 1:])
    return publish_deadline_utc - downstream * 60


def register(w: Worker):
    w.register("sla.plan_day", plan_day)
    w.register("sla.monitor", monitor)


# --------------------------------------------------------------------- helpers

def _today() -> str:
    return _dt.date.today().isoformat()


def _midnight_utc_ts() -> float:
    tomorrow = _dt.datetime.combine(_dt.date.today() + _dt.timedelta(days=1),
                                    _dt.time.min)
    return tomorrow.timestamp()


def _put_setting(sb, key: str, value: dict):
    sb.table("settings").upsert(
        {"tenant_id": _TENANT, "key": key, "value": value},
        on_conflict="tenant_id,key").execute()


def _produced_today(sb, account_id) -> int:
    """Items that reached approved/scheduled/published today. 'prep' items are
    deliberately excluded (DEC-025)."""
    try:
        start = _dt.datetime.combine(_dt.date.today(), _dt.time.min).isoformat() + "Z"
        res = (sb.table("board_items").select("id", count="exact")
               .in_("status", ["approved", "scheduled", "published"])
               .eq("account_id", str(account_id))
               .gte("created_at", start).execute())
        return int(res.count or 0)
    except Exception:
        return 0


def classify(quota: int, produced: int, now_ts: float,
             deadlines: list, minutes_per_post: int = SLA_MINUTES_PER_POST) -> str:
    """Pure function so it is unit-testable (DEC-022 heuristic).

    deadlines: epoch targets for each post slot (len == quota).
    Returns one of: done / on_track / at_risk / behind / breached.
    """
    if produced >= quota:
        return "done"
    remaining = quota - produced
    # Physically impossible to fit the remaining posts before midnight?
    midnight = _midnight_utc_ts()
    if now_ts + remaining * minutes_per_post * 60 > midnight:
        return "breached"
    # Next unmet slot deadline
    unmet = deadlines[produced:] if produced < len(deadlines) else []
    nxt = unmet[0] if unmet else midnight
    if now_ts > nxt:
        return "behind"
    if now_ts + minutes_per_post * 60 > nxt:
        return "at_risk"
    return "on_track"


# --------------------------------------------------------------------- jobs

def plan_day(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    date = _today()
    plans = {}
    if sb is not None:
        for acct in (active_accounts(sb) or []):
            quota = max(1, int(acct.get("posts_per_day") or 1))
            end = account_deadline_utc(acct)                    # 14:00 Asia/Dubai default
            start = end - (24 - SLA_WINDOW_START_H) * 3600      # production window opens
            step = (end - start) / quota
            deadlines = [round(start + step * (i + 1)) for i in range(quota)]
            cfg = acct.get("config") or {}
            plans[str(acct["id"])] = {
                "handle": acct.get("handle"), "quota": quota,
                "deadlines": deadlines, "date": date,
                "deadline_utc": round(end),
                "deadline_local": cfg.get("sla_deadline") or SLA_DEADLINE_LOCAL,
                "timezone": cfg.get("sla_timezone") or SLA_TIMEZONE,
            }
        try:
            _put_setting(sb, "sla_plan", {"date": date, "accounts": plans})
        except Exception as e:
            bus.agent("coo", f"sla plan write failed: {str(e)[:100]}", "warn",
                      "sla_plan_err", job_id=job.id)
    if plans:
        bus.agent("coo", f"🗓️ SLA plan for {date}: "
                         + ", ".join(f"@{p['handle']}×{p['quota']}" for p in plans.values()),
                  "info", "sla_plan", job_id=job.id)
    # self-schedule tomorrow's plan (idempotent per date)
    j = Job(job_type="sla.plan_day", payload={"date": date},
            priority=Priority.LOW, scheduled_for=_midnight_utc_ts() + 60,
            idempotency_key=f"slaplan:{(_dt.date.today() + _dt.timedelta(days=1)).isoformat()}")
    w.queue.enqueue(j)
    w.queue.complete(job, {"ok": True, "accounts": len(plans)})


def monitor(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    now = time.time()
    status_out = {"checked_at": int(now), "accounts": {}}

    if sb is not None:
        # ---- load today's plan (fall back to on-the-fly quota if missing)
        plan = {}
        try:
            res = (sb.table("settings").select("value").eq("tenant_id", _TENANT)
                   .eq("key", "sla_plan").execute())
            v = (res.data or [{}])[0].get("value") or {}
            if v.get("date") == _today():
                plan = v.get("accounts") or {}
        except Exception:
            plan = {}

        behind_accounts = []
        for acct in (active_accounts(sb) or []):
            aid = str(acct["id"])
            quota = int((plan.get(aid) or {}).get("quota")
                        or acct.get("posts_per_day") or 1)
            deadlines = (plan.get(aid) or {}).get("deadlines") or []
            produced = _produced_today(sb, aid)
            state = classify(quota, produced, now, deadlines)
            status_out["accounts"][aid] = {
                "handle": acct.get("handle"), "quota": quota,
                "produced": produced, "state": state,
            }
            if state in ("behind", "breached"):
                behind_accounts.append((acct, state, quota - produced))

        # ---- 3) self-prioritize: stamp deadlines on their queued jobs so
        #         fair_claim_order pulls them ahead of everything else.
        for acct, state, missing in behind_accounts:
            try:
                sb.table("jobs").update({"deadline": now + 600}) \
                  .eq("status", "queued").eq("account_id", str(acct["id"])) \
                  .is_("deadline", "null").execute()
            except Exception:
                pass
            bus.agent("coo", f"⏱️ @{acct.get('handle','?')} is {state} on today's SLA "
                             f"({missing} post(s) short) — its jobs now claim first",
                      "warn", "sla_" + state, job_id=job.id, account_id=acct["id"])
            # ---- 4) breach → founder desk
            if state == "breached":
                try:
                    sb.table("ceo_recommendations").insert({
                        "severity": "critical", "category": "sla",
                        "recommendation": f"🚨 SLA breach: @{acct.get('handle','?')} cannot meet today's quota",
                        "reasoning": f"{missing} post(s) still owed and the remaining time "
                                     f"before midnight UTC is less than {SLA_MINUTES_PER_POST} min/post. "
                                     f"Check the activity feed for the blocking step.",
                        "projected_roi": 0.0, "projected_value_usd": 0.0,
                        "action_url": "/dashboard/studio",
                        "day": _dt.date.today().isoformat(),
                    }).execute()
                except Exception:
                    pass

        # ---- 4b) REQ-SLASTAGE-1: stamp per-stage deadlines on queued jobs that
        #          do not have one yet. One central place beats touching every
        #          spawn site, and fair_claim_order does the rest.
        stamped = 0
        for acct in (active_accounts(sb) or []):
            try:
                dl = account_deadline_utc(acct)
                rows = (sb.table("jobs").select("id,job_type")
                        .eq("status", "queued").eq("account_id", str(acct["id"]))
                        .is_("deadline", "null").limit(200).execute().data) or []
                for r in rows:
                    sd = stage_deadline(r.get("job_type", ""), dl)
                    sb.table("jobs").update({"deadline": sd}).eq("id", r["id"]).execute()
                    stamped += 1
            except Exception:
                continue
        if stamped:
            bus.agent("coo", f"⏱️ stamped stage deadlines on {stamped} queued job(s)",
                      "info", "sla_stamp", job_id=job.id)

        # ---- 4c) REQ-COSTPOST-1: the ROI denominator. Cost optimisation is
        #          meaningless without it — v5.9.5 cut spend 83% while producing
        #          nothing, which reads as success on every cost metric.
        try:
            _write_cost_per_post(sb, bus, job)
        except Exception:
            pass

        # ---- 4d) REQ-BACKOFF-RESET: writer jobs parked with "no model" are
        #          serving a 30-minute sentence handed down when the free tier
        #          was dead. Once the ladder is healthy again that wait is pure
        #          lost SLA — release them to run on the next claim.
        try:
            _release_no_model_backoffs(sb, bus, job, now)
        except Exception:
            pass

        # ---- 5) stuck-job self-heal (crash recovery between reboots)
        try:
            res = (sb.table("jobs")
                   .update({"status": "queued", "claimed_at": None,
                            "error": "sla.monitor: requeued stuck in_progress"})
                   .eq("status", "in_progress")
                   .lt("claimed_at", now - SLA_STUCK_JOB_S).execute())
            healed = len(res.data or [])
            if healed:
                bus.agent("ops", f"🩹 requeued {healed} job(s) stuck in_progress "
                                 f">{SLA_STUCK_JOB_S // 60}min", "warn",
                          "sla_selfheal", job_id=job.id)
        except Exception:
            pass

        try:
            _put_setting(sb, "sla_status", status_out)
        except Exception:
            pass

    # self-schedule next monitor pass (idempotent per interval bucket)
    nxt = now + SLA_MONITOR_INTERVAL_S
    j = Job(job_type="sla.monitor", payload={}, priority=Priority.LOW,
            scheduled_for=nxt,
            idempotency_key=f"slamon:{int(nxt // SLA_MONITOR_INTERVAL_S)}")
    w.queue.enqueue(j)
    w.queue.complete(job, {"ok": True, "accounts": len(status_out["accounts"])})


def _write_cost_per_post(sb, bus, job):
    """settings.cost_per_post — spend today / posts published today, plus the
    all-time figure. Written every monitor pass so the founder can see whether
    cost control is producing value or just suppressing output (REQ-COSTPOST-1)."""
    start = _dt.datetime.combine(_dt.date.today(), _dt.time.min).isoformat() + "Z"
    try:
        led = sb.table("run_ledger").select("cost_usd").gte("created_at", start).execute()
        spend_today = sum(float(x.get("cost_usd") or 0) for x in (led.data or []))
    except Exception:
        spend_today = 0.0
    try:
        pub_today = int((sb.table("board_items").select("id", count="exact")
                         .eq("status", "published").gte("created_at", start)
                         .execute()).count or 0)
    except Exception:
        pub_today = 0
    try:
        led_all = sb.table("run_ledger").select("cost_usd").execute()
        spend_all = sum(float(x.get("cost_usd") or 0) for x in (led_all.data or []))
        pub_all = int((sb.table("board_items").select("id", count="exact")
                       .eq("status", "published").execute()).count or 0)
    except Exception:
        spend_all, pub_all = 0.0, 0
    payload = {
        "spend_today_usd": round(spend_today, 4),
        "published_today": pub_today,
        "cost_per_post_today": round(spend_today / pub_today, 4) if pub_today else None,
        "spend_all_time_usd": round(spend_all, 4),
        "published_all_time": pub_all,
        "cost_per_post_all_time": round(spend_all / pub_all, 4) if pub_all else None,
        "at": int(time.time()),
    }
    _put_setting(sb, "cost_per_post", payload)
    if pub_today:
        bus.agent("cfo", f"💵 cost per published post today: ${payload['cost_per_post_today']:.4f} "
                         f"({pub_today} post(s), ${spend_today:.2f})",
                  "info", "cost_per_post", job_id=job.id)


LADDER_HEALTHY_MIN = int(os.environ.get("LADDER_HEALTHY_MIN", "2"))


def ladder_is_healthy(report: dict) -> bool:
    """Pure + testable. Healthy = enough usable rungs and not flagged below floor."""
    if not report:
        return False
    if report.get("below_floor"):
        return False
    return int(report.get("usable_count") or 0) >= LADDER_HEALTHY_MIN


def _release_no_model_backoffs(sb, bus, job, now: float):
    """Pull forward jobs delayed purely because no model was available."""
    try:
        row = (sb.table("settings").select("value").eq("key", "free_ladder_report")
               .limit(1).execute().data)
        report = (row or [{}])[0].get("value") or {}
    except Exception:
        return
    if not ladder_is_healthy(report):
        return
    try:
        rows = (sb.table("jobs").select("id,error,scheduled_for")
                .eq("status", "queued").eq("job_type", "creative.write_script")
                .gt("scheduled_for", now).limit(50).execute().data) or []
    except Exception:
        return
    released = 0
    for r in rows:
        err = (r.get("error") or "").lower()
        if "no model" not in err and "no free provider" not in err:
            continue
        try:
            sb.table("jobs").update({"scheduled_for": now}).eq("id", r["id"]).execute()
            released += 1
        except Exception:
            continue
    if released:
        bus.agent("coo", f"⏩ free ladder healthy again ({report.get('usable_count')} rungs) — "
                         f"released {released} writer job(s) from no-model backoff",
                  "success", "backoff_released", job_id=job.id)
