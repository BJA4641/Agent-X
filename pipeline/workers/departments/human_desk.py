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
    w.queue.complete(job, {"ok": True, "synced": added})
    _reschedule(w)


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


def _reschedule(w: Worker):
    j = Job(job_type="human_desk.sync", payload={}, priority=Priority.LOW,
            scheduled_for=time.time() + 20,
            idempotency_key=f"desksync:{int(time.time()//20)}")
    w.queue.enqueue(j)
