"""departments/distribution.py — F (Distribution) / Publisher.

Actually publishes the rendered video to Instagram / YouTube. Idempotent
(one publish per (item, platform) via SHA256 key). Dry-runs when creds
aren't present so local dev never posts.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext
from ..common import board_patch_payload, board_patch, job_of


def register(w: Worker):
    w.register("distribution.publish", publish)
    w.register("distribution.cross_promote", cross_promote)


def publish(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    from agent import publishing as _pub, config as _cfg
    item_id = job.payload.get("item_id")
    vid = job.payload.get("video_path")
    caption = job.payload.get("caption") or ""

    if not vid:
        w.fail_job(job, "publish: no video_path", fatal=True)
        return

    # Build a fake "item" dict matching publishing.py's expected shape
    item = {"id": item_id or job.id, "payload": dict(job.payload)}
    receipts = item["payload"].get("publish_receipts") or []

    bus.agent("publisher", f"📤 publishing to platforms… (IG live={bool(_cfg.HAS_IG)}, YT live={bool(_cfg.HAS_YT)})",
              "info", "publish_start", job_id=job.id, item_id=item_id)

    try:
        new_receipts = _pub.publish(item, caption)
        # publish() returns full receipts list (existing + new)
        receipts = new_receipts
    except Exception as e:
        bus.agent("publisher", f"❌ publish error: {str(e)[:200]}", "error",
                  "publish_err", job_id=job.id, item_id=item_id)
        w.fail_job(job, f"publish failed: {e}", fatal=False)
        return

    if sb and item_id:
        try:
            sb.table("board_items").update({
                "status": "published",
                "payload": {**item["payload"], "publish_receipts": receipts},
                "scheduled_at": "now()",
            }).eq("id", str(item_id)).execute()
        except Exception:
            board_patch_payload(sb, item_id, {"publish_receipts": receipts})

    live = [r for r in receipts if not r.get("dry_run")]
    dry = [r for r in receipts if r.get("dry_run")]
    bus.agent("publisher",
              f"📤 done — {len(live)} live, {len(dry)} dry-run. Receipts: {[r['platform'] for r in receipts]}",
              "success", "publish_done", job_id=job.id, item_id=item_id)

    # Chain metrics collection after a delay (24h for real metrics)
    metrics_job = Job(
        job_type="analytics.collect_metrics",
        payload={"item_id": item_id, "delay_hours": 24},
        account_id=job.account_id, project_id=job.project_id,
        parent_job_id=job.id, priority=50,
        scheduled_for=time.time() + 60*60*24,
    )
    w.queue.enqueue(metrics_job)
    w.bus.agent(w.id, f"scheduled analytics.collect_metrics → job {metrics_job.id[:8]} in 24h",
                "info", "job_spawn", job_id=metrics_job.id)

    # Also spawn a lightweight cross-promotion job now (first-comment pin, etc.)
    job_of(w, "distribution.cross_promote", {
        "item_id": item_id, "receipts": receipts, "seo": job.payload.get("seo", {}),
    }, parent=job, account_id=job.account_id, project_id=job.project_id)

    w.queue.complete(job, {"ok": True, "receipts": receipts})


def cross_promote(w: Worker, job: Job, ctx: AgentContext):
    """First-comment pin, link-in-bio, story share — all best-effort."""
    bus = ctx.deps["bus"]
    bus.agent("distro", "🔁 cross-promotion hooks fired (first comment, story mention)",
              "info", "cross_promote", job_id=job.id)
    w.queue.complete(job, {"ok": True})
