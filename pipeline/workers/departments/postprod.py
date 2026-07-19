"""departments/postprod.py — E (Post-Production).

Polish step:
  * Verifies the rendered file exists and is non-tiny.
  * Runs any cross-platform repurposing (clips, aspect ratios).
  * Hands off to risk.scan_content → distribution.publish.
"""
from __future__ import annotations
import os, time
from agentcore import Worker, Job, AgentContext, FatalError
from ..common import board_patch_payload, job_of


MIN_VIDEO_BYTES = 20_000  # 20KB — below this is definitely a stub/corruption


def register(w: Worker):
    w.register("post.polish", polish)


def polish(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    vid = job.payload.get("video_path")
    item_id = job.payload.get("item_id")

    # 1) post-verifier: file exists and is big enough
    if not vid or not os.path.exists(vid):
        w.fail_job(job, f"render output missing: {vid}", fatal=True)
        return
    size = os.path.getsize(vid)
    if size < MIN_VIDEO_BYTES:
        bus.agent("composer", f"⚠️ render file suspiciously small ({size}b) — failing",
                  "warn", "render_small", job_id=job.id, item_id=item_id)
        w.fail_job(job, f"render output too small: {size}b", fatal=False)
        return
    bus.agent("composer", f"🎞️ video verified: {size/1024/1024:.1f}MB", "success",
              "post_verify", job_id=job.id, item_id=item_id)

    # 2) distribution repurposing (cross-platform cuts) — best-effort
    repurp = {}
    try:
        from agent import distribution as _d
        repurp = _d.repurpose(job.payload.get("script", {}),
                              job.payload.get("topic", ""),
                              item_id=item_id) or {}
    except Exception as e:
        bus.agent("distro", f"🔁 repurpose skipped (non-fatal): {str(e)[:100]}",
                  "warn", "repurp_skip", job_id=job.id)

    if sb and item_id:
        board_patch_payload(sb, item_id, {"repurpose": repurp})

    # Transition board state to approved (legacy state machine)
    if sb and item_id:
        board_patch_payload(sb, item_id, {})
        try:
            sb.table("board_items").update({"status": "approved"}).eq("id", str(item_id)).execute()
        except Exception:
            pass

    # Hand off: Risk scan → Monetization → Publish
    bus.agent("qa", "🔍 handing off to Risk → Monetize → Publish", "info", "post_done",
              job_id=job.id, item_id=item_id)
    job_of(w, "risk.scan_content", {
        "item_id": item_id,
        "video_path": vid,
        "caption": job.payload.get("caption_text", ""),
        "script": job.payload.get("script", {}),
        "captions": job.payload.get("captions", {}),
        "seo": job.payload.get("seo", {}),
        "_next_step": "monetization.inject",
    }, parent=job, account_id=job.account_id, project_id=job.project_id,
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "size_bytes": size})
