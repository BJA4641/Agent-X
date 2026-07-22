"""departments/editorial.py — C (Editorial).

Takes a portfolio decision ("produce N posts for account X") and plans
specific topics from strategy/competitor/trend data, inserting them into
the board and kicking off creative.write_script for each.

v5.3 FIXES:
  * BUDGET: preflight check before LLM/ideation costs anything.
  * KILL SWITCH: if on, ideation is skipped cleanly (no rejections).
  * NICHE AWARENESS: topics are filtered/angled to the ACCOUNT's niche
    (cats, finance, ai_tools, ...) instead of always returning AI-tool
    topics. Strategy is called with the account niche; evergreen
    fallbacks are niche-matched; generic AI content is dropped when
    the active account isn't AI-related.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, Priority, ledger as _l
from ..common import (board_add, board_patch, brand_context_for,
                      load_account, job_of, first_active_account,
                      kill_switch, hard_budget_ok, remaining_budget)


def register(w: Worker):
    w.register("editorial.ideate", ideate)
    w.register("editorial.plan_one", plan_one)


def ideate(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    account_id = job.payload.get("account_id") or job.account_id
    target = int(job.payload.get("target_posts") or 1)

    # ----- BUDGET / KILL SWITCH / CEO PREFLIGHT -----
    if kill_switch():
        bus.agent("strategist", "⏸ kill switch on — ideation skipped",
                  "info", "ideate_paused", job_id=job.id)
        w.queue.complete(job, {"ok": True, "paused": True})
        return
    # v5.5 CEO gate for ideation
    if sb:
        from ..common import ceo_decide
        d = ceo_decide(sb, "ideate", account_id=account_id, est_cost=0.02,
                       department="editorial", topic="", item_id=None)
        if d["decision"] == "deny":
            bus.agent("ceo", f"👔 CEO denied ideation: {d['reason']}", "warn", "ceo_deny_ideate", job_id=job.id)
            w.queue.complete(job, {"ok": False, "denied": d["reason"]})
            return
        if d["decision"] == "delay":
            bus.agent("ceo", f"👔 CEO delay ideation: {d['reason']}", "warn", "ceo_delay_ideate", job_id=job.id)
            w.queue._update_row(job, {"status":"queued","scheduled_for":time.time()+3600,"error":d["reason"]})
            return
    if not hard_budget_ok(next_cost_usd=0.02):
        bus.agent("cfo", f"⏸ budget too thin to ideate (${remaining_budget():.3f} left) — skipping",
                  "warn", "ideate_budget", job_id=job.id)
        w.queue.complete(job, {"ok": True, "budget_blocked": True})
        return

    account = load_account(sb, account_id) if account_id else None
    niche = (account or {}).get("niche") or ""
    acct_name = (account or {}).get("name") or (account or {}).get("handle") or str(account_id or "?")[:8]

    bus.agent("strategist", f"📋 ideating {target} topic(s) for @{acct_name} (niche: {niche or 'general'})",
              "info", "ideate_start", job_id=job.id)

    topics = _pick_topics(target, account=account, account_id=account_id)
    if not topics:
        bus.agent("strategist", "no topics chosen — standing down this tick",
                  "warn", "ideate_empty", job_id=job.id)
        w.queue.complete(job, {"ok": True, "planned": 0})
        return

    for topic, bucket in topics[:target]:
        item_row = {"bucket": bucket, "v2": True, "account_id": str(account_id), "niche": niche}
        row = board_add(sb, topic, item_row, status="idea", account_id=account_id) if sb else {"id": None, "topic": topic}
        bus.agent("planner", f"📅 queued: \"{topic[:80]}\" [{bucket}]", "info",
                  "plan_queued", job_id=job.id, item_id=row.get("id"))
        job_of(w, "editorial.plan_one", {
            "item_id": row.get("id"), "topic": topic, "bucket": bucket,
        }, parent=job, account_id=account_id, project_id=job.project_id,
           priority=Priority.HIGH)

    w.queue.complete(job, {"ok": True, "planned": len(topics[:target]), "niche": niche})


def plan_one(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    topic = job.payload["topic"]
    item_id = job.payload.get("item_id")
    account_id = job.account_id or job.payload.get("account_id")
    brand = brand_context_for(sb, account_id)
    bus.agent("strategist", f"📋 briefing writers for: \"{topic[:80]}\"", "info",
              "brief_ready", job_id=job.id, item_id=item_id)

    # Before handing to creative, run cfo.preflight by emitting an event and
    # spawning cfo first if budget is a concern — but for Phase 2 we inline
    # a fast check to avoid spending when over-budget.
    if kill_switch():
        bus.agent("strategist", "⏸ kill switch on — brief held", "warn", "brief_held", job_id=job.id)
        w.queue.complete(job, {"ok": False, "paused": True})
        return

    job_of(w, "creative.write_script", {
        "item_id": item_id, "topic": topic,
        "bucket": job.payload.get("bucket", "experiment"),
        "brand_context": brand,
        "rewrite_attempt": 0,
    }, parent=job, account_id=account_id, project_id=job.project_id,
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "item_id": item_id, "topic": topic})


def _is_generic_ai(low: str) -> bool:
    """True if a topic is generic-AI content (blocked for non-AI niches)."""
    return any(w in low for w in ("chatgpt", "claude", "gemini", "ai tool", "gpt",
                                  " ai ", "free ai", "ai app", "ai setting", "a.i"))


def _pick_topics(n: int, account=None, account_id=None) -> list:
    """Return [(topic, bucket)] — niche-aware."""
    niche = ((account or {}).get("niche") or "").lower().replace("_", " ").replace("-", " ")
    name = (account or {}).get("name") or (account or {}).get("handle") or ""

    topics: list = []
    seen: set = set()

    # 1) Ask legacy strategy for topics; pass niche hint if available
    try:
        from agent import strategy as _strat
        # If strategy.plan supports a niche/account hint, use it; else fall back.
        try:
            planned = _strat.plan(n=n, niche=niche, account_name=name) or []
        except TypeError:
            planned = _strat.plan(n=n) or []
        for t in planned:
            topic = ""
            bucket = "experiment"
            if isinstance(t, dict):
                topic = t.get("topic",""); bucket = t.get("bucket","experiment")
            elif isinstance(t, (list, tuple)) and t:
                topic = str(t[0]); bucket = str(t[1]) if len(t)>1 else "experiment"
            elif isinstance(t, str):
                topic = t
            topic = topic.strip()
            low = topic.lower()
            # v5.7.1: legacy strategy's corpus is AI-niche — filter it like trends
            if niche and niche not in ("ai", "ai tools", "ai_tools", "tech") and _is_generic_ai(" " + low + " "):
                continue
            if topic and low not in seen:
                topics.append((topic[:120], bucket))
                seen.add(low)
    except Exception as e:
        print(f"[editorial] strategy.plan failed: {e}")

    # 2) Fill from scout trends — prefer items whose title contains niche keywords
    if len(topics) < n:
        try:
            from agent import scout as _s
            trends = _s.recent_trends(n * 3) or []
            niche_kw = niche.split() if niche else []
            # First pass: niche matches
            for t in trends:
                if len(topics) >= n: break
                title = t if isinstance(t, str) else (t.get("title") if isinstance(t, dict) else "")
                if not title: continue
                low = title.lower()
                if niche_kw and any(kw in low for kw in niche_kw) and low not in seen:
                    topics.append((title[:120], "trend")); seen.add(low)
            # Second pass: any trend (but if niche is set, skip generic AI ones)
            for t in trends:
                if len(topics) >= n: break
                title = t if isinstance(t, str) else (t.get("title") if isinstance(t, dict) else "")
                if not title: continue
                low = title.lower()
                if niche and niche not in ("ai","ai tools","ai_tools","tech") and _is_generic_ai(" " + low + " "):
                    continue  # skip generic AI topics if this isn't an AI account
                if low not in seen:
                    topics.append((title[:120], "trend")); seen.add(low)
        except Exception:
            pass

    # 3) Niche-matched evergreen backstops
    for topic in _niche_evergreens(niche):
        if len(topics) >= n: break
        if topic.lower() not in seen:
            topics.append((topic, "evergreen")); seen.add(topic.lower())

    return topics[:n]


def _niche_evergreens(niche: str) -> list:
    """Return clone-the-angle evergreen topics tailored to niche."""
    n = niche.lower()
    if any(k in n for k in ("skin", "beauty", "glow", "makeup", "self care", "selfcare", "grooming")):
        return [
            "The 3-second test that shows if your moisturizer actually works",
            "Why your skin looks worse right after washing (1-step fix)",
            "The $8 drugstore product dermatologists quietly recommend",
            "3 skincare mistakes that age you faster",
            "The morning habit that clears skin faster than any serum",
        ]
    if any(k in n for k in ("cat", "kitten", "pet", "dog", "animal")):
        return [
            "The one thing your cat does that means 'I love you'",
            "Why cats stare at walls at 3am (the real reason)",
            "The toy cats go crazy for that costs $0",
            "3 mistakes new cat owners make in week one",
            "The sound that instantly calms an anxious cat",
        ]
    if any(k in n for k in ("financ","money","side hustle","invest","wealth","crypto")):
        return [
            "The side hustle that takes 30 minutes a day",
            "3 money habits that made me a millionaire by 30",
            "Why your savings account is losing you money",
            "The $0 tool that tracks every subscription automatically",
            "One credit-card mistake that costs $1000s",
        ]
    if any(k in n for k in ("fit","gym","workout","health","weight")):
        return [
            "The 8-minute morning workout that changed my body",
            "3 protein mistakes almost everyone makes",
            "Why your ab workouts aren't showing (fix this)",
            "The stretch that fixes desk-posture in 30 seconds",
            "One trick to make cardio feel easy",
        ]
    if any(k in n for k in ("cook","food","recipe","meal","kitchen")):
        return [
            "The 5-minute dinner I make when I'm exhausted",
            "3 ingredients that make anything taste restaurant-good",
            "The knife skill chefs hide from home cooks",
            "Why your pasta never tastes as good as at restaurants",
            "One seasoning that goes on everything",
        ]
    # Default / ai / tech / productivity niche
    return [
        "3 AI tools you didn't know existed this week",
        "The free AI feature that replaces a paid app",
        "One AI shortcut that saves 30 minutes a day",
        "The AI setting everyone should turn off",
        "The hidden AI button that does the work for you",
    ]
