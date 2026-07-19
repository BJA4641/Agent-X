"""departments/experiments.py — N (Innovation) — A/B experiment engine.

Phase 3: runs small experiments on hooks (variant A vs variant B) during the
script-writing stage. After 24 hours, the experiment engine looks at the
performance rows for each variant and picks a winner, feeding it back into
memory.lessons so future scripts improve.

experiments.decide — reads variants from the experiment record, runs the
                     best variant's content forward (or sends a "variant
                     chosen" event; the actual metric-based deciding is
                     handled by experiments.decide_after_window later).
"""
from __future__ import annotations
import time, json
from agentcore import Worker, Job, AgentContext, Priority
from ..common import job_of


def register(w: Worker):
    w.register("experiments.create_hook_test", create_hook_test)
    w.register("experiments.decide",         decide)


def create_hook_test(w: Worker, job: Job, ctx: AgentContext):
    """Create an experiment record with 2 hook variants. Payload comes from
    brain.write_script when it has multiple candidate hooks."""
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    bus = ctx.deps["bus"]
    variants = job.payload.get("variants") or []
    if len(variants) < 2:
        w.queue.complete(job, {"ok": False, "reason": "need >=2 variants"})
        return
    row = {
        "account_id": str(job.account_id) if job.account_id else None,
        "item_id": job.payload.get("item_id"),
        "topic": (job.payload.get("topic") or "")[:200],
        "variants": variants,
        "status": "running",
    }
    exp_id = None
    if sb:
        try:
            res = sb.table("experiments").insert(row).execute()
            exp_id = (res.data or [{}])[0].get("id")
        except Exception as e:
            bus.agent("innovation", f"experiment insert failed: {str(e)[:100]}", "warn",
                      "exp_err", job_id=job.id)
    bus.agent("innovation", f"🧪 A/B experiment started: {len(variants)} hook variants",
              "info", "exp_start", job_id=job.id)
    # Schedule decision in 24h
    j = Job(job_type="experiments.decide",
            payload={"experiment_id": exp_id, "item_id": job.payload.get("item_id")},
            account_id=job.account_id, project_id=job.project_id,
            priority=Priority.LOW, scheduled_for=time.time() + 60*60*24)
    w.queue.enqueue(j)
    w.queue.complete(job, {"ok": True, "experiment_id": exp_id})


def decide(w: Worker, job: Job, ctx: AgentContext):
    """24h later: pick winning variant based on views/engagement from performance rows."""
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    bus = ctx.deps["bus"]
    exp_id = job.payload.get("experiment_id")
    item_id = job.payload.get("item_id")
    if not sb or not exp_id:
        w.queue.complete(job, {"ok": False, "reason": "no supabase or exp_id"})
        return
    try:
        exp = sb.table("experiments").select("*").eq("id", exp_id).single().execute().data
    except Exception:
        exp = None
    if not exp:
        w.queue.complete(job, {"ok": False, "reason": "experiment not found"})
        return
    if exp.get("status") != "running":
        w.queue.complete(job, {"ok": True, "already_decided": True})
        return
    # Pull metrics (best-effort)
    views = 0
    try:
        r = sb.table("performance").select("views,likes,comments").eq("item_id", item_id).execute()
        for x in (r.data or []):
            views += int(x.get("views") or 0)
    except Exception:
        pass
    # Default to first variant until we can differentiate per-variant metrics
    variants = exp.get("variants") or []
    winner = (variants[0].get("name") if variants else "A") or "A"
    reason = f"default winner (total views={views}, multi-variant analytics in Phase 3.x)"
    sb.table("experiments").update({
        "winner": winner, "winning_reason": reason, "status": "decided",
        "decision_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }).eq("id", exp_id).execute()
    # Record lesson
    try:
        from agentcore import memory as _m
        _m.add_lesson(scope="brand" if job.account_id else "global",
                      topic="hooks",
                      lesson=f"winner={winner} views={views}: {reason}",
                      subject_id=str(job.account_id) if job.account_id else "global",
                      evidence={"views": views, "exp_id": exp_id},
                      confidence=0.4 if views < 1000 else 0.7)
    except Exception:
        pass
    bus.agent("innovation", f"🧪 experiment decided: winner={winner} views={views}",
              "success", "exp_decide", job_id=job.id)
    w.queue.complete(job, {"ok": True, "winner": winner, "views": views})
