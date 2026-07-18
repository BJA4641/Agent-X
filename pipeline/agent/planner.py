"""planner.py — the 30-day editorial calendar.

Builds a structured posting plan from the Brand Bible + recent performance.
Output: a list of planned items, each with {date, platform, format, pillar,
topic, hook_type, cta}.

Why this matters: strategy.py currently picks n topics per tick based on RSS
and winner/loser data, but has no concept of pillar balance, content mix
ratios (educational/entertaining/community/promo), platform cadence, or
narrative arcs. This module produces a proper calendar every 7 days and
stores it in the `board_items` table as 'idea' rows with metadata, so the
daily produce loop draws from a balanced plan instead of ad-hoc topics.
"""
from __future__ import annotations
import json, time, datetime
from . import config, ledger, board, llm, brand, strategy, analytics

EST_COST = 0.015


def build_week_plan(user_id: str = None, days: int = 7) -> list:
    """Plan the next `days` days and queue as idea rows. Returns the plan."""
    grounding = brand.grounding_block(user_id)
    # Context for the planner
    winners, losers = _recent_performance()
    active_pf = _active_platforms(user_id)
    pillars = _pillars_from_brand(user_id)

    prompt = f"""You are an editorial director for a social media content agency.
Given the Brand Bible, recent performance, and active platforms, produce a
{days}-day content calendar.

BRAND BIBLE:
{grounding}

ACTIVE PLATFORMS: {active_pf}
PILLARS (balance topics across these): {pillars}
RECENT WINNERS (do more of whatever made these work): {json.dumps(winners)}
RECENT LOSERS (avoid these angles): {json.dumps(losers)}
TREND FEED: {json.dumps(strategy.trends(limit=10))}

CONTENT MIX RULES (strictly enforce):
- 40% educational, 25% entertaining, 20% community/social-proof, 15% promotional
- rotate evenly across the pillars
- vary formats (reels, carousels, statics, stories, threads) — not every post a reel
- leave 1 slot/day as "rapid_response" for real-time trends
- cadence per platform per week: instagram 6 reels + 3 carousels + daily stories,
  tiktok 5 shorts (if active), youtube 1 long + 3 shorts (if active),
  linkedin 3 posts (if active), x 5 tweets/threads (if active)

Output a JSON array of planned posts. Each element:
{{"days_from_today": int, "platform": str, "format": str, "pillar": str,
 "topic": str, "bucket": "educational"|"entertaining"|"community"|"promo"|"rapid",
 "hook_type": "curiosity"|"controversy"|"story"|"question"|"stat", "cta": str}}
Output ONLY the JSON array, nothing else."""

    if llm.ready() and ledger.budget_ok(EST_COST):
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=1500)
            plan = json.loads(text[text.find("["): text.rfind("]") + 1])
            ledger.record("planner", model=mlabel, prompt_version="planner_v1", cost_usd=cost)
        except Exception as e:
            ledger.record("planner", ok=False, detail=str(e))
            plan = _fallback_plan(days, active_pf, pillars)
    else:
        plan = _fallback_plan(days, active_pf, pillars)

    # Queue into board
    queued = []
    now = time.time()
    for item in plan[:50]:
        day_offset = int(item.get("days_from_today", 0))
        scheduled_at = now + day_offset * 86400 + _optimal_hour(item.get("platform"), item.get("format"))
        # Skip if we already have a non-failed queued item for this slot
        existing = [i for i in board.list("idea") + board.list("drafted") + board.list("approved") + board.list("scheduled")
                    if i.get("topic") == item["topic"] and abs((i.get("scheduled_at") or 0) - scheduled_at) < 3600]
        if existing:
            continue
        board.add(item["topic"], status="idea",
                  payload={"bucket": item.get("bucket", "educational"),
                           "planned_platform": item.get("platform"),
                           "format": item.get("format", "reel"),
                           "pillar": item.get("pillar"),
                           "hook_type": item.get("hook_type"),
                           "planned_cta": item.get("cta")},
                  scheduled_at=scheduled_at)
        queued.append(item)
    return queued


def _recent_performance() -> tuple[list, list]:
    items = [i for i in board.list("reported")]
    def views(i): return sum((v.get("views", 0)) for v in (i.get("payload", {}).get("metrics") or {}).values())
    ranked = sorted(items, key=views, reverse=True)
    winners = [{"topic": i["topic"], "views": views(i)} for i in ranked[:5]]
    losers = [{"topic": i["topic"], "views": views(i)} for i in ranked[-5:]]
    return winners, losers


def _active_platforms(user_id=None) -> list:
    try:
        from . import connections
        return connections.active_platforms_for_user(user_id or config.TENANT_ID)
    except Exception:
        pf = ["instagram"]
        if config.HAS_YT: pf.append("youtube")
        return pf


def _pillars_from_brand(user_id=None) -> list:
    p = brand.profile_for(user_id)
    import re
    m = re.search(r"CONTENT PILLARS:\s*(.+)", p)
    if m:
        return [s.strip() for s in m.group(1).strip("[]").split(",") if s.strip()]
    return ["educational", "entertaining", "behind-the-scenes", "offers"]


def _optimal_hour(platform: str, format: str) -> int:
    """Return seconds-offset for best posting hour (rough defaults)."""
    hours = {"instagram": 9, "tiktok": 19, "youtube": 15, "linkedin": 9, "x": 12, "pinterest": 20}
    import random
    return hours.get(platform, 10) * 3600 + random.randint(0, 55) * 60


def _fallback_plan(days: int, platforms: list, pillars: list) -> list:
    plan = []
    buckets = ["educational"] * 4 + ["entertaining"] * 2 + ["community"] * 2 + ["promo"]
    import random
    for d in range(days):
        for pf in platforms[:2]:  # limit fallback to main two platforms
            plan.append({
                "days_from_today": d,
                "platform": pf, "format": "reel" if pf != "youtube" else "short",
                "pillar": pillars[d % max(1, len(pillars))],
                "topic": f"{pillars[d % max(1,len(pillars))]} tip #{d+1}",
                "bucket": buckets[d % len(buckets)],
                "hook_type": random.choice(["curiosity", "question", "stat"]),
                "cta": "Follow for more.",
            })
    return plan
