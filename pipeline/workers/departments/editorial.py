"""departments/editorial.py — C (Editorial).

Takes a portfolio decision ("produce N posts for account X") and plans
specific topics from strategy/competitor/trend data, inserting them into
the board and kicking off creative.write_script for each.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, Priority, ledger as _l
from ..common import (board_add, board_patch, brand_context_for,
                      load_account, job_of, first_active_account)


def register(w: Worker):
    w.register("editorial.ideate", ideate)
    w.register("editorial.plan_one", plan_one)


def ideate(w: Worker, job: Job, ctx: AgentContext):
    """Pick N topics for the account and queue each as plan_one."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    account_id = job.payload.get("account_id") or job.account_id
    target = int(job.payload.get("target_posts") or 1)

    bus.agent("strategist", f"📋 ideating {target} topic(s) for account {str(account_id)[:8]}",
              "info", "ideate_start", job_id=job.id)

    topics = _pick_topics(target, account_id=account_id)
    if not topics:
        bus.agent("strategist", "no topics chosen — standing down this tick",
                  "warn", "ideate_empty", job_id=job.id)
        w.queue.complete(job, {"ok": True, "planned": 0})
        return

    for topic, bucket in topics[:target]:
        # Insert into legacy board so the existing publishing stack still reads it
        item_row = {"bucket": bucket, "v2": True, "account_id": str(account_id)}
        row = board_add(sb, topic, item_row, status="idea") if sb else {"id": None, "topic": topic}
        bus.agent("planner", f"📅 queued: \"{topic[:80]}\" [{bucket}]", "info",
                  "plan_queued", job_id=job.id, item_id=row.get("id"))
        job_of(w, "editorial.plan_one", {
            "item_id": row.get("id"), "topic": topic, "bucket": bucket,
        }, parent=job, account_id=account_id, project_id=job.project_id,
           priority=Priority.HIGH)

    w.queue.complete(job, {"ok": True, "planned": len(topics[:target])})


def plan_one(w: Worker, job: Job, ctx: AgentContext):
    """Single-item prep: load brand context, then hand off to creative."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    topic = job.payload["topic"]
    item_id = job.payload.get("item_id")
    account_id = job.account_id or job.payload.get("account_id")
    brand = brand_context_for(sb, account_id)
    bus.agent("strategist", f"📋 briefing writers for: \"{topic[:80]}\"", "info",
              "brief_ready", job_id=job.id, item_id=item_id)
    job_of(w, "creative.write_script", {
        "item_id": item_id, "topic": topic,
        "bucket": job.payload.get("bucket", "experiment"),
        "brand_context": brand,
        "rewrite_attempt": 0,
    }, parent=job, account_id=account_id, project_id=job.project_id,
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "item_id": item_id, "topic": topic})


def _pick_topics(n: int, account_id=None) -> list:
    """Return [(topic, bucket)] — uses existing strategy.plan when possible,
    falls back to scout patterns/trends so we always have SOMETHING to produce
    (no more empty-queue burn from LLM plan failures)."""
    topics = []
    try:
        from agent import strategy as _strat
        planned = _strat.plan(n=n) or []
        for t in planned:
            if isinstance(t, dict):
                topics.append((t.get("topic","")[:120], t.get("bucket","experiment")))
            elif isinstance(t, (list, tuple)) and t:
                topics.append((str(t[0])[:120], str(t[1])[:40] if len(t)>1 else "experiment"))
            elif isinstance(t, str):
                topics.append((t[:120], "experiment"))
    except Exception as e:
        print(f"[editorial] strategy.plan failed: {e}")

    if len(topics) < n:
        # Fallback: pull from scout trends
        try:
            from agent import scout as _s
            trends = _s.recent_trends(n * 2) or []
            seen = {t.lower() for t, _ in topics}
            for t in trends:
                title = t if isinstance(t, str) else t.get("title", "")
                if title and title.lower() not in seen:
                    topics.append((title[:120], "trend"))
                    seen.add(title.lower())
                    if len(topics) >= n:
                        break
        except Exception:
            pass

    # Final backstop: curated evergreen angles (clone-the-angle only, no copy)
    EVERGREEN = [
        "3 AI tools you didn't know existed this week",
        "The free AI feature that replaces a paid app",
        "One AI shortcut that saves 30 minutes a day",
        "The AI setting everyone should turn off",
        "The hidden AI button that does the work for you",
    ]
    seen = {t.lower() for t, _ in topics}
    for t in EVERGREEN:
        if len(topics) >= n:
            break
        if t.lower() not in seen:
            topics.append((t, "evergreen"))
            seen.add(t.lower())

    return topics[:n]
