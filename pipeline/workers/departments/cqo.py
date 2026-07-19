"""departments/cqo.py — O (Quality) / CQO.

Runs the centralized quality gate. The grader (agent.grader) gives scripts
a 1-10 score on 6 dimensions; the CQO agent turns that into a
QualityGate decision with blocking PASS/FAIL, enforces max-rewrite caps
to prevent the infinite-retry burn problem, and can escalate to a human.
"""
from __future__ import annotations
import time
from agentcore import (Worker, Job, AgentContext, QualityGate, FatalError,
                      Priority, HumanEscalation)
from ..common import job_of


MAX_REWRITES = 2  # hard cap — matches user's "stop burning money on failures" mandate
PASS_THRESHOLD = 8.0
MIN_DIM = 6


def register(w: Worker):
    w.register("cqo.grade_script", grade_script)


def grade_script(w: Worker, job: Job, ctx: AgentContext):
    from agent import grader as _g
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()

    item_id = job.payload.get("item_id")
    script = job.payload.get("script") or {}
    account_id = job.account_id or job.payload.get("account_id")
    project_id = job.project_id or job.payload.get("project_id")
    rewrite_attempt = int(job.payload.get("rewrite_attempt", 0))

    if not script or not script.get("beats"):
        w.fail_job(job, "cqo.grade_script: no script in payload", fatal=True)
        return

    bus.agent("cqo", f"🛡️ grading script — attempt {rewrite_attempt+1}/{MAX_REWRITES+1}",
              "info", "cqo_grade_start", job_id=job.id)
    verdict = _g.grade_post(script, account_id=account_id, project_id=project_id,
                            item_id=item_id)
    overall = float(verdict.get("overall") or 0)
    scores = verdict.get("scores") or {}
    fix = (verdict.get("fix") or verdict.get("fix_instruction") or "weak content")[:400]
    passed = bool(verdict.get("passed")) and overall >= PASS_THRESHOLD
    if passed:
        # Guard against any single dimension below MIN_DIM slipping through
        dims = [scores.get(k, 10) for k in ("hook","visuals","pacing","audio","caption","cta")]
        if dims and min(dims) < MIN_DIM:
            passed = False
            fix = f"weak dimension (min={min(dims)}): {fix}"

    qg = QualityGate(
        passed=passed,
        score=overall,
        dimension_scores={k: float(scores.get(k, 0)) for k in scores},
        reasons=[verdict.get("notes", "")[:400]],
        fix_instruction=fix if not passed else "publish",
        blocker=not passed,
    )

    if passed:
        bus.agent("cqo", f"✅ script PASSED — {overall:.1f}/10. Moving to render.",
                  "success", "cqo_pass", job_id=job.id)
        # Chain into render
        job_of(w, "creative.render", {
            "item_id": item_id, "script": script, "style": job.payload.get("style", "cinemagraph"),
        }, parent=job, priority=job.priority)
        w.queue.complete(job, {"ok": True, "quality": qg.model_dump()})
        return

    # Failed — rewrite or kill
    bus.agent("cqo", f"❌ script FAILED — {overall:.1f}/10. {fix[:120]}",
              "warn", "cqo_fail", job_id=job.id)
    if rewrite_attempt < MAX_REWRITES:
        bus.agent("cqo", f"requesting rewrite ({rewrite_attempt+1}/{MAX_REWRITES})",
                  "info", "cqo_rewrite", job_id=job.id)
        job_of(w, "creative.write_script", {
            "item_id": item_id,
            "topic": job.payload.get("topic") or script.get("title") or "",
            "account_id": account_id,
            "project_id": project_id,
            "previous_script": script,
            "grade_feedback": fix,
            "rewrite_attempt": rewrite_attempt + 1,
        }, parent=job, priority=job.priority)
        w.queue.complete(job, {"ok": False, "retried": True, "quality": qg.model_dump()})
        return

    # Hard reject — no more retries. Record and kill.
    bus.agent("cqo", f"⛔ FINAL REJECT after {rewrite_attempt+1} attempts — {fix[:120]}",
              "error", "cqo_final_reject", job_id=job.id)
    try:
        from agentcore import memory as _m
        _m.add(role="cqo",
               content=f"FINAL REJECT overall={overall:.1f}: {fix}",
               account_id=account_id, project_id=project_id,
               metadata={"grade": overall, "item_id": item_id})
    except Exception:
        pass
    # Mark board_item as rejected (legacy board)
    if sb and item_id:
        try:
            from ..common import board_patch
            board_patch(sb, item_id, status="rejected", payload_patch={
                "script": script,
                "rejection": {"reason": "grade_fail", "fix": fix, "score": overall,
                              "rewrites": rewrite_attempt},
            })
        except Exception:
            pass
    w.queue.complete(job, {"ok": False, "rejected": True, "quality": qg.model_dump()})
