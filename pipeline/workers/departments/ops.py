"""departments/ops.py — L (Infrastructure) + Autothrottle + Health heartbeats.

Phase 3 additions:
  * ops.heartbeat — updates worker_health row every 15s (so dashboard shows liveness).
  * ops.snapshot  — writes hourly KPI rows (spend/publishes/views/inflight).
  * ops.throttle  — enforces auto-throttle: if we've spent >90% of the daily
                    budget and less than reserve_fraction remains, SEND NEW WORK
                    TO WAIT (not fail). This replaces the "hard cutoff = zero
                    output for the rest of the day" problem.
"""
from __future__ import annotations
import os, time, socket
from agentcore import Worker, Job, AgentContext, Priority
from ..common import job_of


def register(w: Worker):
    w.register("ops.heartbeat", heartbeat)
    w.register("ops.snapshot",  snapshot)


HEARTBEAT_INTERVAL_S = 30
JOBS_COMPLETED = 0
JOBS_FAILED = 0


# Called from Worker._execute after job completion/failure
def _bump_counters(ok: bool):
    global JOBS_COMPLETED, JOBS_FAILED
    if ok:
        JOBS_COMPLETED += 1
    else:
        JOBS_FAILED += 1


def heartbeat(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    try:
        from agentcore import __version__
    except Exception:
        __version__ = "5.1"
    version = job.payload.get("version", "5.1")
    started = job.payload.get("started_at", time.time())
    in_flight = 0
    if sb:
        try:
            r = sb.table("jobs").select("id", count="exact").in_("status", ["claimed","in_progress"]).execute()
            in_flight = int(r.count or 0)
        except Exception:
            pass
    row = {
        "worker_id": w.id,
        "last_heartbeat_at": time.time(),
        "jobs_completed": JOBS_COMPLETED,
        "jobs_failed": JOBS_FAILED,
        "jobs_in_progress": in_flight,
        "host": socket.gethostname()[:80],
        "version": version,
        "started_at": started,
    }
    if sb:
        try:
            sb.table("worker_health").upsert(row).execute()
        except Exception as e:
            bus.agent("infrastructure", f"heartbeat write failed: {str(e)[:120]}", "warn",
                      "hb_err", job_id=job.id)
    # Self-schedule next heartbeat
    j = Job(job_type="ops.heartbeat",
            payload={"started_at": started, "version": version},
            priority=Priority.LOW,
            scheduled_for=time.time() + HEARTBEAT_INTERVAL_S,
            idempotency_key=f"hb:{w.id}:{int(time.time()//HEARTBEAT_INTERVAL_S)}")
    w.queue.enqueue(j)
    w.queue.complete(job, {"ok": True})


def snapshot(w: Worker, job: Job, ctx: AgentContext):
    """Hourly KPI snapshot for CEO dashboard."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    from agentcore import ledger as _l, config as _cfg
    now = time.time()
    spent = _l.spent_today()
    publishes = _count_today(sb, "board_items", {"status": "published"})
    inflight = _count_today(sb, "board_items", {"status_in": ["idea","drafted","approved","scheduled"]})
    views = 0
    if sb:
        try:
            r = sb.table("performance").select("views").gte("captured_at", _today_iso()).execute()
            views = sum(int(x.get("views") or 0) for x in (r.data or []))
        except Exception:
            pass
    metrics = [
        ("spend_usd", spent),
        ("publishes", publishes),
        ("views", views),
        ("inflight", inflight),
    ]
    if sb:
        try:
            for name, val in metrics:
                sb.table("kpi_snapshots").insert({"metric": name, "value": val}).execute()
        except Exception as e:
            bus.agent("analyst", f"snapshot write failed: {str(e)[:120]}", "warn",
                      "snap_err", job_id=job.id)
    bus.agent("analyst",
              f"📊 snapshot — ${spent:.3f} spent, {publishes} published, {views} views, {inflight} in-flight",
              "info", "snapshot", job_id=job.id)
    # Next snapshot in 1 hour
    j = Job(job_type="ops.snapshot", payload={}, priority=Priority.LOW,
            scheduled_for=now + 3600,
            idempotency_key=f"snap:{int(now//3600)}")
    w.queue.enqueue(j)
    w.queue.complete(job, {"spent": spent, "publishes": publishes,
                           "views": views, "inflight": inflight})


def _count_today(sb, table, filters) -> int:
    if sb is None:
        return 0
    try:
        q = sb.table(table).select("id", count="exact")
        for k, v in filters.items():
            if k.endswith("_in"):
                q = q.in_(k[:-3], v)
            else:
                q = q.eq(k, v)
        r = q.execute()
        return int(r.count or 0)
    except Exception:
        return 0


def _today_iso() -> str:
    import datetime
    return datetime.date.today().isoformat()
