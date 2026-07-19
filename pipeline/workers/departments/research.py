"""departments/research.py — G (Research).

Runs the scout (live Reddit/HN/Google News + viral pattern library) on a
schedule and stores trend rows so Editorial has fresh data to ideate from.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, Priority
from ..common import job_of


def register(w: Worker):
    w.register("research.scout_run", scout_run)


def scout_run(w: Worker, job: Job, ctx: AgentContext):
    """Refresh trend cache. Cheap (zero LLM cost) so we run every 30min."""
    bus = ctx.deps["bus"]
    bus.agent("scout", "🔭 refreshing trend feeds (Reddit / Google News / HN / patterns)",
              "info", "scout_start", job_id=job.id)
    try:
        from agent import scout as _s
        # scout.ensure_seeded() writes pattern rows; scout.run() pulls live.
        try:
            _s.ensure_seeded()
        except Exception:
            pass
        added = 0
        try:
            added = int(_s.run(limit_per_source=6) or 0)
        except TypeError:
            # run() may not return a count in older versions
            try:
                _s.run()
                added = 1
            except Exception:
                added = 0
        bus.agent("scout", f"🔭 trends refreshed — {added} new items", "success",
                  "scout_done", job_id=job.id)
    except Exception as e:
        bus.agent("scout", f"🔭 scout error (non-fatal): {str(e)[:160]}", "warn",
                  "scout_err", job_id=job.id)
    w.queue.complete(job, {"ok": True})
