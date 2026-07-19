"""departments/finance.py — CFO / K (Finance).

Responsibilities:
  * Hard daily-budget gate (stop producing if budget exhausted).
  * AUTO-THROTTLE (Phase 3): when >90% spent and reserve fraction enabled,
    FUTURE work is scheduled for tomorrow instead of being killed outright,
    so we don't burn the entire budget by noon and go silent the rest of day.
  * Per-job cost estimates + pre-flight approval.
  * Kill-switch check (global + remote settings).
  * End-of-day spend report job.
"""
from __future__ import annotations
import time, datetime
from agentcore import Worker, Job, AgentContext, EventType, Priority, FatalError
from ..common import kill_switch
from agentcore import ledger as _l, config as _cfg


def register(w: Worker):
    w.register("cfo.preflight",    preflight)
    w.register("cfo.daily_report", daily_report)
    w.register("cfo.killswitch_check", kill_check)


# ---------- preflight ----------
def preflight(w: Worker, job: Job, ctx: AgentContext):
    """Runs BEFORE any creative work begins. Applies three gates:
       1. Kill switch ON    → fatal block.
       2. Budget 100% spent → fatal block (no more money today).
       3. Budget >90% spent → if autothrottle ON and job is low-priority,
              RESCHEDULE to tomorrow instead of blocking (keeps output flowing).
    """
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    spent = _l.spent_today()
    cap = _daily_budget(sb)
    ks = kill_switch()
    reasons = []
    if ks:
        reasons.append("kill switch is ON")
    if spent >= cap:
        reasons.append(f"daily budget exhausted: spent ${spent:.3f} / ${cap:.2f}")
    if reasons:
        msg = "CFO BLOCK: " + "; ".join(reasons)
        bus.agent("cfo", "💰 " + msg, "error", "budget_block", job_id=job.id)
        w.fail_job(job, msg, fatal=True)
        return

    # Auto-throttle: reschedule non-urgent jobs across the day
    pct = spent / max(cap, 0.01)
    throttle = _autothrottle_setting(sb)
    if throttle.get("on") and pct > (1.0 - float(throttle.get("reserve_fraction", 0.1))):
        # In the throttle zone: bump this job 30-120 minutes out, but do NOT fail
        if job.priority < Priority.HIGH:
            delay = 60 + int(60 * pct * 60)  # more delay as we near cap
            job.scheduled_for = time.time() + delay
            job.status = _jobstatus_queued()
            try:
                w.queue._update_row(job, {
                    "status": "queued",
                    "scheduled_for": job.scheduled_for,
                    "error": f"throttled: spent ${spent:.3f}/${cap:.2f}, delaying {delay}s",
                })
            except Exception:
                pass
            bus.agent("cfo",
                      f"⏱️ throttling — spent {pct*100:.0f}% of budget, delaying low-priority job {delay//60}m",
                      "info", "throttle_delay", job_id=job.id)
            return  # don't mark complete or fail; just leave queued

    bus.agent("cfo", f"💰 preflight OK — spent ${spent:.3f}/${cap:.2f} ({pct*100:.0f}%)",
              "success", "budget_ok", job_id=job.id)
    w.queue.complete(job, {"ok": True, "spent_usd": spent, "budget_usd": cap,
                           "pct": pct})


def daily_report(w: Worker, job: Job, ctx: AgentContext):
    spent = _l.spent_today()
    cap = _cfg.DAILY_BUDGET_USD
    ctx.deps["bus"].agent(
        "cfo", f"daily spend: ${spent:.4f} / ${cap:.2f} ({spent/cap*100:.0f}% used)",
        "info", "daily_report", job_id=job.id)
    w.queue.complete(job, {"spent_usd": spent, "budget_usd": cap})


def kill_check(w: Worker, job: Job, ctx: AgentContext):
    # Lightweight tick job — just logs whether things are paused
    on = kill_switch()
    ctx.deps["bus"].agent(
        "cfo",
        "kill switch ARMED — all production paused" if on
        else "kill switch OFF — production may proceed",
        "warn" if on else "info", "kill_check", job_id=job.id)
    w.queue.complete(job, {"killswitch_on": on})


# ---------- helpers ----------

def _daily_budget(sb) -> float:
    """Read budget from settings table (live), fallback to env."""
    if sb:
        try:
            r = sb.table("settings").select("value").eq("tenant_id", _cfg.TENANT_ID).eq("key", "daily_budget").limit(1).execute()
            if r.data:
                return float((r.data[0].get("value") or {}).get("usd") or _cfg.DAILY_BUDGET_USD)
        except Exception:
            pass
    return _cfg.DAILY_BUDGET_USD


def _autothrottle_setting(sb) -> dict:
    if sb:
        try:
            r = sb.table("settings").select("value").eq("tenant_id", _cfg.TENANT_ID).eq("key", "autothrottle").limit(1).execute()
            if r.data:
                v = r.data[0].get("value") or {}
                return {"on": bool(v.get("on", True)),
                        "reserve_fraction": float(v.get("reserve_fraction", 0.1))}
        except Exception:
            pass
    return {"on": True, "reserve_fraction": 0.1}


def _jobstatus_queued():
    from agentcore import JobStatus
    return JobStatus.QUEUED
