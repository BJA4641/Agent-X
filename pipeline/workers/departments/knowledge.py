"""departments/knowledge.py — M (Knowledge / Memory).

Periodic maintenance:
  - Prunes events older than 30 days.
  - Consolidates grade feedback into lessons.
  - Writes a daily memory digest.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext


def register(w: Worker):
    w.register("knowledge.summarize_day", summarize_day)


def summarize_day(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    from agentcore import ledger as _l
    spent = _l.spent_today()
    bus.agent("analyst", f"📚 day summary — ${spent:.4f} spent", "info",
              "day_summary", job_id=job.id)
    w.queue.complete(job, {"ok": True, "spent_usd": spent})
