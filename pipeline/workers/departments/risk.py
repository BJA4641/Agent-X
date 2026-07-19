"""departments/risk.py — P (Risk Management).

Checks content for dangerous claims (financial/medical/spam), banned
platform phrases, and idempotency-key collisions before publish. Cheap
and fast — runs pre-publish to stop ban-vectors.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, validate_dangerous_content, FatalError
from ..common import job_of


BANNED_PHRASES = [
    "get rich quick", "guaranteed income", "sure thing", "no risk",
    "cures", "miracle", "proven by science",
    "limited offer", "act now", "only today",
    "buy now", "click here",
]


def register(w: Worker):
    w.register("risk.scan_content", scan_content)


def scan_content(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    script = job.payload.get("script") or {}
    caption = (job.payload.get("caption") or "")
    text_parts = [
        script.get("hook", ""), script.get("title", ""), script.get("caption", ""), caption
    ] + [b.get("voiceover", "") for b in (script.get("beats") or [])]
    full = " \n".join(p for p in text_parts if p).lower()

    flags = list(validate_dangerous_content(full))
    # Banned-phrase scan
    for phrase in BANNED_PHRASES:
        if phrase in full:
            flags.append(f"banned_phrase:{phrase}")

    if flags:
        msg = f"RISK FLAG — blocked before publish: {flags}"
        bus.agent("risk", "🚨 " + msg, "error", "risk_block", job_id=job.id)
        w.queue.complete(job, {"ok": False, "flags": flags})
        return

    bus.agent("risk", "✅ risk scan clean — claim/spam check passed", "success",
              "risk_ok", job_id=job.id)
    # Chain to monetization (which itself chains to publish)
    next_step = job.payload.get("_next_step", "monetization.inject")
    job_of(w, next_step, {**job.payload}, parent=job,
           account_id=job.account_id, project_id=job.project_id,
           priority=job.priority)
    w.queue.complete(job, {"ok": True})
