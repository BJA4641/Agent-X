"""departments/human_desk.py — Human Desk (founder approvals).

When an agent raises HumanEscalation, the worker calls queue.wait_human()
which writes a row into jobs with _escalation payload. The `human_desk.sync`
job copies those escalations into the `escalations` table so the web UI
has a clean queue to display. Resolves (approve/reject) are made from the
UI via a new /api/human/ route; a separate job `human_desk.poll` rehydrates
resolved escalations back into their originating jobs.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, JobStatus, Priority


def register(w: Worker):
    w.register("human_desk.sync", sync)
    w.register("human_desk.rescan", rescan)


def sync(w: Worker, job: Job, ctx: AgentContext):
    """Copy wait_human jobs into the escalations table (dedupe by job_id)."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    if sb is None:
        w.queue.complete(job, {"ok": False, "reason": "no supabase"})
        _reschedule(w)
        return
    try:
        r = (sb.table("jobs").select("*")
             .eq("status", "wait_human").limit(50).execute())
        wait_jobs = r.data or []
    except Exception as e:
        bus.agent("human_desk", f"sync scan failed: {str(e)[:120]}", "warn",
                  "desk_scan_err", job_id=job.id)
        wait_jobs = []

    added = 0
    for j in wait_jobs:
        esc = (j.get("payload") or {}).get("_escalation") or {}
        # Already-escalated? Check existing row by job_id
        try:
            existing = (sb.table("escalations").select("id")
                        .eq("job_id", j["id"]).limit(1).execute())
            if existing.data:
                continue
        except Exception:
            pass
        sb.table("escalations").insert({
            "job_id": j["id"],
            "item_id": j.get("brand_id") or None,
            "account_id": j.get("account_id"),
            "severity": esc.get("severity", "ask"),
            "summary": esc.get("summary", "needs review"),
            "options": esc.get("options", []),
            "context": esc.get("context", {}),
            "deadline_hours": esc.get("deadline_hours", 24),
        }).execute()
        added += 1
        bus.agent("human_desk", f"👤 escalation queued: {esc.get('summary','?')[:80]}",
                  "warn", "escalation", job_id=j["id"])
    if added:
        bus.agent("human_desk", f"👤 {added} escalation(s) awaiting founder review",
                  "warn", "desk_summary", job_id=job.id)

    # v5.8.2 CONTENT BRIDGE — the missing link that meant NOTHING ever rendered:
    # Studio's Approve button only flips board_items.status to 'approved';
    # no one ever picked those up. This sweep turns founder approvals into
    # real render jobs, and logs approve/reject decisions as lessons.
    try:
        _approved_sweep(w, job, sb, bus)
    except Exception as e:
        bus.agent("human_desk", f"approved-sweep error: {str(e)[:120]}", "warn",
                  "sweep_err", job_id=job.id)

    w.queue.complete(job, {"ok": True, "synced": added})
    _reschedule(w)


def _approved_sweep(w: Worker, job: Job, sb, bus, max_renders: int = 2):
    """1) Enqueue creative.render for founder-approved items that have no video
       yet (idempotent — one render job per item, ever).
       2) Write a lesson for every fresh approve/reject so the brain learns
       the founder's taste."""
    if sb is None:
        return
    rows = (sb.table("board_items").select("id,status,topic,payload,account_id")
            .in_("status", ["approved", "rejected"])
            .order("updated_at", desc=True).limit(25).execute().data) or []
    renders = 0
    for it in rows:
        payload = it.get("payload") or {}
        item_id = it.get("id")
        # --- (2) founder-decision lessons, once per item
        if not payload.get("lesson_logged"):
            try:
                from agentcore import memory as _m
                hook = ((payload.get("script") or {}).get("hook") or "")[:90]
                _m.add_lesson(
                    "human_" + it["status"],
                    f"Founder {it['status'].upper()}: \"{(it.get('topic') or '')[:90]}\""
                    + (f" (hook: \"{hook}\")" if hook else ""),
                    account_id=it.get("account_id"),
                    niche=(payload.get("niche") or ""),
                    metadata={"item_id": item_id})
                payload["lesson_logged"] = True
                sb.table("board_items").update({"payload": payload}).eq("id", item_id).execute()
            except Exception:
                pass
        # --- (1) approved + scripted + not yet rendered → render job
        if (it["status"] == "approved" and renders < max_renders
                and (payload.get("script") or {}).get("beats")
                and not payload.get("video_path")
                and not payload.get("render_enqueued")):
            from ..common import job_of as _job_of
            # v5.11.6 REQ-ART-BYPASS: this spawned creative.render DIRECTLY,
            # skipping art.direct entirely. The Art Director (v5.10.0) therefore
            # never ran on a single founder-approved item — every frame was
            # rendered from whatever the writer left in beat.visual_prompt, which
            # is the exact "draw a sentence" problem art direction exists to fix.
            # art.direct is fail-open: it always hands off to creative.render.
            _job_of(w, "art.direct",
                    {"item_id": item_id, "script": payload.get("script"),
                     "topic": it.get("topic") or "",
                     "account_id": it.get("account_id"),
                     "style": payload.get("style")},
                    account_id=it.get("account_id"),
                    idempotency_key=f"art:{item_id}",
                    priority=Priority.HIGH)
            payload["render_enqueued"] = True
            sb.table("board_items").update({"payload": payload}).eq("id", item_id).execute()
            bus.agent("human_desk",
                      f"🎬 founder approved \"{(it.get('topic') or '')[:60]}\" — art direction then render queued",
                      "success", "approve_to_render", job_id=job.id, item_id=item_id)
            renders += 1


def rescan(w: Worker, job: Job, ctx: AgentContext):
    """Look for resolved escalations and move their jobs back to queued/done."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    if sb is None:
        w.queue.complete(job, {"ok": False})
        return
    try:
        r = (sb.table("escalations").select("*")
             .is_("resolved_at", "null").not_.is_("resolution", "null")
             .limit(50).execute())
        rows = r.data or []
    except Exception:
        rows = []

    progressed = 0
    for esc in rows:
        jid = esc.get("job_id")
        if not jid:
            continue
        resolution = esc.get("resolution")
        note = esc.get("resolved_note", "")
        # Mark escalation resolved_at
        sb.table("escalations").update({
            "resolved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }).eq("id", esc["id"]).execute()
        # Unblock the originating job by patching its payload + status
        patch = {
            "status": JobStatus.QUEUED.value,
            "payload": {"_resolution": resolution, "_resolution_note": note},
            "scheduled_for": time.time(),
            "error": None,
        }
        try:
            sb.table("jobs").update(patch).eq("id", jid).execute()
            bus.agent("human_desk", f"✅ resolved {resolution} on job {jid[:8]}",
                      "success", "desk_resolved", job_id=jid)
            progressed += 1
        except Exception as e:
            bus.agent("human_desk", f"resolution apply failed on {jid[:8]}: {str(e)[:100]}",
                      "error", "desk_err", job_id=jid)

    w.queue.complete(job, {"ok": True, "progressed": progressed})
    _reschedule(w)


import os as _os
# v5.9.5: 20s cadence generated ~14,400 sync jobs/week of pure overhead.
# 120s is plenty for an approval desk a human checks a few times a day.
HUMAN_DESK_SYNC_SECONDS = int(_os.environ.get("HUMAN_DESK_SYNC_SECONDS", "120"))


def _reschedule(w: Worker):
    nxt = time.time() + HUMAN_DESK_SYNC_SECONDS
    j = Job(job_type="human_desk.sync", payload={}, priority=Priority.LOW,
            scheduled_for=nxt,
            idempotency_key=f"desksync:{int(nxt // HUMAN_DESK_SYNC_SECONDS)}")
    w.queue.enqueue(j)
