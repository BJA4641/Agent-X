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
SHIP_FLOOR = 7.0  # v5.8.5: after max rewrites, SHIP the best attempt if >= this.


def _claude_final_audit(w, script, item_id, account_id, project_id, job):
    """v5.8.6 — the ONLY place Anthropic is spent in the content loop.

    Free models write, debate and grade every attempt. When a script is about
    to ship (passed or ship-best), Claude runs ONE verification pass (~$0.01).
      returns ("ok", verdict)    Claude agrees → render
              ("veto", verdict)  Claude scores it < SHIP_FLOOR → park for human
              ("skip", None)     audit off / no key / audit errored → render anyway
    Fail-open by design: an audit outage must never stall production."""
    try:
        from agent import config as _cfg
        if not _cfg.get("ANTHROPIC_API_KEY"):
            return "skip", None
        sb = w.deps.get("supabase") and w.deps["supabase"]()
        # v5.8.8 SPEND POLICY: paid thinking is off by default. The Anthropic
        # budget now goes to ONE 10-day strategy retro (strategy.audit) instead
        # of a per-item audit. Opt back in with settings.claude_final_audit={"on":true}.
        from agentcore import costmode as _cm2
        if not _cm2.policy().get("paid_thinking", False):
            opted_in = False
            if sb:
                row = sb.table("settings").select("value").eq("key", "claude_final_audit").limit(1).execute().data
                opted_in = bool(row and (row[0].get("value") or {}).get("on") is True)
            if not opted_in:
                return "skip", None
        from agent import grader as _g2
        v = _g2.grade_post(script, account_id=account_id, project_id=project_id,
                           item_id=item_id, force_claude=True)
        if v.get("skipped"):
            return "skip", None
        overall = float(v.get("overall") or 0)
        if overall < SHIP_FLOOR:
            return "veto", v
        return "ok", v
    except Exception as e:
        bus.agent("cqo", f"final audit errored ({str(e)[:80]}) — shipping on free-council grade", 
                  "warn", "cqo_audit_error", job_id=job.id)
        return "skip", None


def _park_vetoed(w, sb, item_id, script, verdict, job):
    """Claude vetoed the ship — park as drafted with the audit notes for a human."""
    bus.agent("cqo", f"🛑 CLAUDE FINAL AUDIT VETO — {float(verdict.get('overall') or 0):.1f}/10: "
                     f"{(verdict.get('fix') or '')[:120]} — parked for human review.",
              "warn", "cqo_audit_veto", job_id=job.id)
    if sb and item_id:
        try:
            row = sb.table("board_items").select("payload").eq("id", item_id).limit(1).execute().data
            payload = dict((row and row[0].get("payload")) or {})
            payload["script"] = script
            payload["claude_audit"] = {"overall": verdict.get("overall"),
                                       "notes": verdict.get("notes"), "fix": verdict.get("fix")}
            sb.table("board_items").update({"status": "drafted", "payload": payload}).eq("id", item_id).execute()
        except Exception:
            pass
    w.queue.complete(job, {"ok": True, "audit_veto": True, "parked": "drafted"})
                  # Money spent on drafts must produce output — only truly weak
                  # content (<7.0 on every attempt) is thrown away.
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

    # v5.7.1: if the grader could not actually run (budget/LLM gate), do NOT
    # burn money on blind rewrites against a fail-safe score. Park the draft
    # as UNGRADED on the board — the human in Studio is the final gate anyway.
    if verdict.get("skipped"):
        bus.agent("cqo", "⚠️ grader unavailable (budget/LLM) — parking draft UNGRADED for human review, $0 spent",
                  "warn", "cqo_skipped", job_id=job.id)
        if sb and item_id:
            try:
                row = sb.table("board_items").select("payload").eq("id", item_id).limit(1).execute().data
                payload = dict((row and row[0].get("payload")) or {})
                payload["script"] = script
                payload["grade"] = {"skipped": True, "reason": verdict.get("notes", "")}
                sb.table("board_items").update({
                    "status": "drafted", "payload": payload,
                }).eq("id", item_id).execute()
            except Exception:
                pass
        w.queue.complete(job, {"ok": True, "skipped": True, "parked": "drafted"})
        return

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
        # v5.8.6: ONE Claude verification before money is spent on rendering.
        decision, audit = _claude_final_audit(w, script, item_id, account_id, project_id, job)
        if decision == "veto":
            _park_vetoed(w, sb, item_id, script, audit, job)
            return
        if decision == "ok":
            bus.agent("cqo", f"🔏 Claude final audit: {float(audit.get('overall') or 0):.1f}/10 — confirmed.",
                      "success", "cqo_audit_ok", job_id=job.id)
        bus.agent("cqo", f"✅ script PASSED — {overall:.1f}/10. Moving to render.",
                  "success", "cqo_pass", job_id=job.id)
        # v5.8.2 LEARNING: record what worked so future drafts reuse it.
        try:
            from agentcore import memory as _m2
            _m2.add_lesson("grade_pass",
                f"PASSED {overall:.1f}/10 — hook \"{(script.get('hook') or '')[:90]}\" "
                f"on topic \"{(job.payload.get('topic') or script.get('title') or '')[:90]}\"",
                account_id=account_id, project_id=project_id,
                metadata={"overall": overall, "scores": scores, "item_id": item_id})
        except Exception:
            pass
        # v5.9.7 REQ-AUTOAPPROVE-1: opt-in removal of the human gate for
        # high-scoring drafts. OFF by default — see auto_approve_decision.
        auto = False
        try:
            auto = _maybe_auto_approve(w, sb, bus, job, item_id, overall, scores, script)
        except Exception as e:
            bus.agent("cqo", f"auto-approve check errored ({str(e)[:80]}) — human gate kept",
                      "warn", "auto_approve_err", job_id=job.id)
        # Chain into render
        job_of(w, "creative.render", {
            "item_id": item_id, "script": script, "style": job.payload.get("style", "cinemagraph"),
        }, parent=job, priority=job.priority)
        w.queue.complete(job, {"ok": True, "quality": qg.model_dump(), "auto_approved": auto})
        return

    # Failed — rewrite or kill
    bus.agent("cqo", f"❌ script FAILED — {overall:.1f}/10. {fix[:120]}",
              "warn", "cqo_fail", job_id=job.id)
    # v5.8.2 LEARNING: record the concrete failure so writers stop repeating it.
    try:
        from agentcore import memory as _m2
        _m2.add_lesson("grade_fail",
            f"FAILED {overall:.1f}/10 on \"{(job.payload.get('topic') or script.get('title') or '')[:90]}\" — fix: {fix[:200]}",
            account_id=account_id, project_id=project_id,
            metadata={"overall": overall, "scores": scores, "item_id": item_id})
    except Exception:
        pass
    # v5.8.5: remember the BEST attempt so far — it travels with the rewrite chain.
    prev_best = float(job.payload.get("best_overall") or 0)
    best_script, best_overall = (script, overall) if overall >= prev_best else \
        (job.payload.get("best_script") or script, prev_best)

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
            "best_script": best_script,
            "best_overall": best_overall,
        }, parent=job, priority=job.priority)
        w.queue.complete(job, {"ok": False, "retried": True, "quality": qg.model_dump()})
        return

    # v5.8.5 SHIP-BEST: rewrites exhausted. If the best attempt cleared the ship
    # floor, PUBLISH IT instead of torching the money already spent. A 7.8/10
    # reel that ships beats a perfect reel that never exists — volume creates
    # the feedback data the grader itself needs to get better.
    if best_overall >= SHIP_FLOOR:
        # v5.8.6: Claude gets the final word on ship-best too — one call.
        decision, audit = _claude_final_audit(w, best_script, item_id, account_id, project_id, job)
        if decision == "veto":
            _park_vetoed(w, sb, item_id, best_script, audit, job)
            return
        bus.agent("cqo", f"🚢 SHIP-BEST — best attempt {best_overall:.1f}/10 clears the "
                          f"{SHIP_FLOOR:.0f} floor after {rewrite_attempt+1} tries. Rendering it.",
                  "success", "cqo_ship_best", job_id=job.id)
        try:
            from agentcore import memory as _m3
            _m3.add_lesson("grade_pass",
                f"SHIPPED-AT-{best_overall:.1f}/10 (below the {PASS_THRESHOLD:.0f} bar, above the "
                f"{SHIP_FLOOR:.0f} floor) — topic \"{(job.payload.get('topic') or best_script.get('title') or '')[:90]}\"",
                account_id=account_id, project_id=project_id,
                metadata={"overall": best_overall, "shipped_below_bar": True, "item_id": item_id})
        except Exception:
            pass
        job_of(w, "creative.render", {
            "item_id": item_id, "script": best_script,
            "style": job.payload.get("style", "cinemagraph"),
            "shipped_at_grade": best_overall,
        }, parent=job, priority=job.priority)
        w.queue.complete(job, {"ok": True, "shipped_best": True, "grade": best_overall,
                               "quality": qg.model_dump()})
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


# ------------------------------------------------- v5.9.7 REQ-AUTOAPPROVE-1

AUTO_APPROVE_DEFAULT_MIN = 8.5   # deliberately strict: well above SHIP_FLOOR (7.0)


def auto_approve_decision(*, enabled: bool, overall: float, min_score: float,
                          dimension_scores: dict, min_dim: float,
                          risk_flags: list = None) -> tuple:
    """Pure, testable gate for skipping the human approval step.

    Design stance (DEC-038): autonomous publishing is OFF by default. Removing
    the founder from the publish path is a safety decision, not a throughput
    tweak, so it must be opted into explicitly per tenant and it holds content
    to a materially higher bar than the normal ship floor.

    Returns (approve: bool, reason: str).
    """
    if not enabled:
        return False, "auto-approve disabled (human gate active)"
    if risk_flags:
        return False, f"risk flags present: {', '.join(map(str, risk_flags[:3]))}"
    if overall < min_score:
        return False, f"score {overall:.1f} below auto-approve bar {min_score:.1f}"
    dims = [float(v) for v in (dimension_scores or {}).values()]
    if dims and min(dims) < min_dim:
        return False, f"weakest dimension {min(dims):.1f} below {min_dim:.1f}"
    return True, f"score {overall:.1f} >= {min_score:.1f}, all dimensions >= {min_dim:.1f}"


def _auto_approve_config(sb) -> tuple:
    """settings.auto_approve = {"on": true, "min_score": 8.5}. Default: OFF."""
    if sb is None:
        return False, AUTO_APPROVE_DEFAULT_MIN
    try:
        row = (sb.table("settings").select("value").eq("key", "auto_approve")
               .limit(1).execute().data)
        v = (row or [{}])[0].get("value") or {}
        return bool(v.get("on") is True), float(v.get("min_score") or AUTO_APPROVE_DEFAULT_MIN)
    except Exception:
        return False, AUTO_APPROVE_DEFAULT_MIN


def _maybe_auto_approve(w, sb, bus, job, item_id, overall, scores, script) -> bool:
    """Flip a passed item straight to 'approved' when the tenant has opted in
    and the score clears the higher bar. Returns True if approved."""
    enabled, min_score = _auto_approve_config(sb)
    risk = []
    try:
        payload = (script or {}).get("risk_flags") or []
        risk = list(payload) if isinstance(payload, (list, tuple)) else []
    except Exception:
        risk = []
    ok, reason = auto_approve_decision(
        enabled=enabled, overall=float(overall or 0), min_score=min_score,
        dimension_scores={k: float(v) for k, v in (scores or {}).items()},
        min_dim=MIN_DIM, risk_flags=risk)
    if not ok:
        if enabled:
            bus.agent("human_desk", f"🖐️ held for founder review — {reason}", "info",
                      "auto_approve_held", job_id=job.id, item_id=item_id)
        return False
    try:
        from ..common import board_patch
        board_patch(sb, item_id, status="approved")
    except Exception:
        return False
    bus.agent("human_desk", f"🤖 AUTO-APPROVED — {reason}. Founder review skipped per "
                            f"settings.auto_approve; render proceeds.",
              "success", "auto_approved", job_id=job.id, item_id=item_id)
    return True
