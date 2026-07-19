"""departments/finance.py — CFO / K (Finance).

Responsibilities:
  * Hard daily-budget gate (stop producing if budget exhausted).
  * Per-job cost estimates + pre-flight approval.
  * Kill-switch check (global + remote settings).
  * End-of-day spend report job.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, EventType, Priority, FatalError
from ..common import kill_switch, OUTPUT_DIR
from agentcore import ledger as _l, config as _cfg


def register(w: Worker):
    w.register("cfo.preflight",    preflight)
    w.register("cfo.daily_report", daily_report)
    w.register("cfo.killswitch_check", kill_check)


# ---------- preflight ----------
def preflight(w: Worker, job: Job, ctx: AgentContext):
    """Runs BEFORE any creative work begins. If budget spent or kill switch is
    on, BLOCK the parent workflow and emit a clear dashboard message — NO
    money spent, no retries, no infinite loops."""
    bus = ctx.deps["bus"]
    spent = _l.spent_today()
    cap = _cfg.DAILY_BUDGET_USD
    ks = kill_switch()
    reasons = []
    if ks:
        reasons.append("kill switch is ON (set KILL_SWITCH=0 or flip settings.kill_switch off)")
    if spent >= cap:
        reasons.append(f"daily budget exhausted: spent ${spent:.3f} / ${cap:.2f}")
    if reasons:
        msg = "CFO BLOCK: " + "; ".join(reasons)
        bus.agent("cfo", msg, "error", "budget_block", job_id=job.id)
        # No retry — budget resets naturally the next calendar day.
        w.fail_job(job, msg, fatal=True)
        return
    bus.agent("cfo", f"preflight OK — spent ${spent:.3f}/${cap:.2f}", "success",
              "budget_ok", job_id=job.id)
    w.queue.complete(job, {"ok": True, "spent_usd": spent, "budget_usd": cap})


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
