"""workers/departments/scorecard.py — v5.11.13 REQ-AGENT-SCORECARD.

The question this answers
-------------------------
"How can we know for sure that they are evolving and self-improving?"

The honest starting point: **these agents do not self-improve in the machine
learning sense.** No weights change. Nothing trains. What can genuinely improve
is four things, and each is measurable:

  1. the prompts and skills they are given      (we change these)
  2. the lessons written to memory              (they write these)
  3. the models available and how we route them (we change these)
  4. the founder's accept/reject feedback       (you provide this)

So "are they getting better" is not a feeling, it is a trend line. This module
computes that trend from data the system already stores, and writes it to
settings.agent_scorecard where the dashboard and the MCP connector can read it.

Deliberately unflattering by design: if the numbers are not moving, the report
says so. A scorecard that always shows progress is a scorecard measuring nothing.

Metrics, and why each was chosen:
  * pass_rate         — share of graded scripts that passed. THE quality signal.
                        At the time of writing: 18 graded, 0 passed.
  * avg_grade         — mean overall score. Moves before pass_rate does, so it
                        is the early indicator that prompt changes are working.
  * rewrites_per_pass — attempts needed per accepted script. Falls when the
                        writer internalises the rubric; the cost metric.
  * cost_per_approved — money per item the founder actually accepted. The only
                        cost figure that reflects value rather than activity.
  * approval_rate     — founder approvals ÷ (approvals + rejections). Taste
                        alignment. Cannot be gamed by the agents.
  * overhead_ratio    — self-maintenance events ÷ production events. Was ~99%.
  * error_rate        — errors ÷ events, per agent. Reliability.
"""
from __future__ import annotations
import datetime as _dt
import os
import time

from agentcore import Worker, Job, AgentContext

WINDOW_DAYS = int(os.environ.get("SCORECARD_WINDOW_DAYS", "7"))

# Agents whose events are overhead rather than content production.
OVERHEAD_AGENTS = {"queue", "coo", "ceo", "cfo", "cto", "ops", "system", "agentx-v5"}
PRODUCTION_AGENTS = {"brain", "composer", "visuals", "voice", "editor", "architect",
                     "cqo", "grader", "publisher", "distro", "seo"}


def register(w: Worker):
    w.register("ops.scorecard", build)


def _pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def compute(rows_grades, rows_board, rows_events, spend_usd) -> dict:
    """Pure function over already-fetched rows, so it is unit-testable.

    rows_grades: [{"action": "cqo_pass"|"cqo_fail", "overall": float|None}]
    rows_board:  [{"status": str}]
    rows_events: [{"agent": str, "status": str}]
    """
    passed = sum(1 for r in rows_grades if r.get("action") == "cqo_pass")
    failed = sum(1 for r in rows_grades if r.get("action") == "cqo_fail")
    graded = passed + failed
    overalls = [float(r["overall"]) for r in rows_grades
                if r.get("overall") not in (None, "")]

    approved = sum(1 for r in rows_board if r.get("status") in ("approved", "published"))
    rejected = sum(1 for r in rows_board if r.get("status") == "rejected")

    overhead = sum(1 for e in rows_events if e.get("agent") in OVERHEAD_AGENTS)
    production = sum(1 for e in rows_events if e.get("agent") in PRODUCTION_AGENTS)
    errors = sum(1 for e in rows_events if e.get("status") in ("error", "critical"))

    return {
        "window_days": WINDOW_DAYS,
        "scripts_graded": graded,
        "pass_rate_pct": _pct(passed, graded),
        "avg_grade": round(sum(overalls) / len(overalls), 2) if overalls else None,
        "rewrites_per_pass": round(graded / passed, 2) if passed else None,
        "approved": approved,
        "rejected": rejected,
        "approval_rate_pct": _pct(approved, approved + rejected),
        "spend_usd": round(float(spend_usd or 0), 4),
        "cost_per_approved_usd": round(float(spend_usd) / approved, 4) if approved else None,
        "overhead_events": overhead,
        "production_events": production,
        "overhead_ratio_pct": _pct(overhead, overhead + production),
        "error_events": errors,
        "error_rate_pct": _pct(errors, len(rows_events)) if rows_events else None,
        "at": int(time.time()),
    }


def verdict(now: dict, prev: dict = None) -> dict:
    """Compare against the previous run. States plainly when nothing moved."""
    if not prev:
        return {"trend": "first_measurement",
                "note": "No previous scorecard. This run is the baseline — "
                        "improvement can only be claimed against it, not asserted."}
    moves, better, worse = {}, 0, 0
    for key, higher_is_better in (("pass_rate_pct", True), ("avg_grade", True),
                                  ("approval_rate_pct", True),
                                  ("rewrites_per_pass", False),
                                  ("cost_per_approved_usd", False),
                                  ("overhead_ratio_pct", False),
                                  ("error_rate_pct", False)):
        a, b = prev.get(key), now.get(key)
        if a is None or b is None:
            continue
        delta = round(b - a, 3)
        if delta == 0:
            continue
        moves[key] = delta
        improved = (delta > 0) if higher_is_better else (delta < 0)
        better += 1 if improved else 0
        worse += 0 if improved else 1
    if not moves:
        return {"trend": "flat", "moves": {},
                "note": "Nothing measurable changed. Prompt or skill edits since "
                        "the last run have not yet shown up in outcomes."}
    return {"trend": "improving" if better > worse else
                     "regressing" if worse > better else "mixed",
            "moves": moves, "improved_metrics": better, "worsened_metrics": worse}


def build(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    if sb is None:
        w.queue.complete(job, {"ok": False, "reason": "no_db"})
        return
    since = (_dt.datetime.utcnow() - _dt.timedelta(days=WINDOW_DAYS)).isoformat() + "Z"

    try:
        ev = (sb.table("agent_events").select("agent,status,action,message")
              .gte("created_at", since).limit(5000).execute().data) or []
    except Exception:
        ev = []
    grades = [{"action": e.get("action"), "overall": _grade_from(e.get("message"))}
              for e in ev if e.get("action") in ("cqo_pass", "cqo_fail")]
    try:
        board = (sb.table("board_items").select("status")
                 .gte("created_at", since).limit(2000).execute().data) or []
    except Exception:
        board = []
    try:
        led = (sb.table("run_ledger").select("cost_usd")
               .gte("created_at", since).limit(5000).execute().data) or []
        spend = sum(float(r.get("cost_usd") or 0) for r in led)
    except Exception:
        spend = 0.0

    now = compute(grades, board, ev, spend)
    prev = None
    try:
        row = (sb.table("settings").select("value").eq("key", "agent_scorecard")
               .limit(1).execute().data)
        prev = ((row or [{}])[0].get("value") or {}).get("current")
    except Exception:
        prev = None
    now["verdict"] = verdict(now, prev)

    try:
        sb.table("settings").upsert(
            {"tenant_id": os.environ.get("TENANT_ID", "me"), "key": "agent_scorecard",
             "value": {"current": now, "previous": prev}},
            on_conflict="tenant_id,key").execute()
    except Exception:
        pass

    pr = now.get("pass_rate_pct")
    bus.agent("analyst",
              f"📊 scorecard — {now['scripts_graded']} graded, "
              f"pass {pr if pr is not None else '—'}%, "
              f"approval {now.get('approval_rate_pct') or '—'}%, "
              f"overhead {now.get('overhead_ratio_pct') or '—'}%, "
              f"trend: {now['verdict']['trend']}",
              "info", "scorecard", job_id=job.id)
    w.queue.complete(job, {"ok": True, "scorecard": now})


def _grade_from(message: str):
    """Pull the numeric grade out of a cqo event message like '7.2/10'."""
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", message or "")
    return float(m.group(1)) if m else None
