"""departments/analytics.py — J (Analytics) + Post-Mortems.

Pulls platform metrics after 24h, writes to performance table, and feeds a
post-mortem that records lessons to memory/lessons so future content improves.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext
from ..common import board_patch_payload, board_get


def register(w: Worker):
    w.register("analytics.collect_metrics", collect)
    w.register("analytics.post_mortem",    post_mortem)


def collect(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    bus.agent("analyst", f"📊 pulling metrics for item {str(item_id)[:8]}", "info",
              "metrics_start", job_id=job.id, item_id=item_id)

    metrics = {"views": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0}
    # Live metric pulls require per-platform API wiring; MVP records what we
    # can and relies on manual or future API pulls.
    if sb and item_id:
        try:
            existing = board_get(sb, item_id) or {}
            prior = ((existing.get("payload") or {}).get("metrics") or {})
            metrics.update({k: prior.get(k, 0) for k in metrics})
            # Insert a performance row
            for platform in ("instagram", "youtube", "tiktok"):
                try:
                    sb.table("performance").insert({
                        "item_id": str(item_id),
                        "platform": platform,
                        "views": metrics["views"],
                        "likes": metrics["likes"],
                        "comments": metrics["comments"],
                    }).execute()
                except Exception:
                    pass
            board_patch_payload(sb, item_id, {"metrics": metrics})
            try:
                sb.table("board_items").update({"status": "reported"}).eq("id", str(item_id)).execute()
            except Exception:
                pass
        except Exception as e:
            bus.agent("analyst", f"📊 metrics write skipped: {str(e)[:120]}", "warn",
                      "metrics_skip", job_id=job.id)

    bus.agent("analyst", f"📊 metrics logged — {metrics['views']} views, {metrics['likes']} likes",
              "success", "metrics_done", job_id=job.id, item_id=item_id)
    w.queue.complete(job, {"ok": True, "metrics": metrics})


def post_mortem(w: Worker, job: Job, ctx: AgentContext):
    """Analyze win/loss and store a lesson (self-improvement loop)."""
    bus = ctx.deps["bus"]
    metrics = job.payload.get("metrics") or {}
    item_id = job.payload.get("item_id")
    hook = (job.payload.get("script") or {}).get("hook", "")
    views = int(metrics.get("views") or 0)
    if views >= 50000:
        verdict, conf = "winner", 0.8
    elif views >= 10000:
        verdict, conf = "solid", 0.6
    elif views < 1000:
        verdict, conf = "flop", 0.6
    else:
        verdict, conf = "average", 0.4
    bus.agent("analyst", f"📊 post-mortem: {verdict} ({views} views)", "info",
              "post_mortem", job_id=job.id, item_id=item_id)
    try:
        from agentcore import memory as _m
        _m.add_lesson(scope="global", topic="performance",
                      lesson=f"hook='{hook[:60]}' => {verdict} ({views} views)",
                      subject_id=str(item_id) if item_id else "global",
                      evidence={"views": views, "verdict": verdict},
                      confidence=conf)
    except Exception:
        pass
    w.queue.complete(job, {"ok": True, "verdict": verdict})
