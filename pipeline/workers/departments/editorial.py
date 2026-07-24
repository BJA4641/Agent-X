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
import os
import time
from agentcore import Worker, Job, AgentContext, Priority, ledger as _l
from ..common import (board_add, board_patch, brand_context_for,
                      load_account, job_of, first_active_account,
                      kill_switch, hard_budget_ok, remaining_budget)


def register(w: Worker):
    w.register("editorial.ideate", ideate)
    w.register("editorial.plan_one", plan_one)
    w.register("editorial.plan_carousel", plan_carousel)


def plan_carousel(w: Worker, job: Job, ctx: AgentContext):
    """v5.8 BATCH4: pick one niche topic and brief creative for a 5-slide
    carousel (image post). Cheap format, real algorithmic reach."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    account_id = job.account_id or job.payload.get("account_id")
    account = None
    if sb and account_id:
        try:
            res = sb.table("project_accounts").select("*").eq("id", str(account_id)).execute()
            account = (res.data or [None])[0]
        except Exception:
            account = None
    picked = _pick_topics(1, account=account, account_id=account_id)
    if not picked:
        w.queue.complete(job, {"ok": False, "reason": "no_topic"})
        return
    topic, bucket = picked[0]
    row = board_add(sb, f"[carousel] {topic}",
                    {"bucket": bucket, "format": "carousel"},
                    status="idea", account_id=account_id) if sb else {"id": None}
    item_id = row.get("id")
    bus.agent("strategist", f"🖼️ carousel brief: \"{topic[:70]}\"", "info",
              "carousel_brief", job_id=job.id, item_id=item_id, account_id=account_id)
    job_of(w, "creative.write_carousel", {
        "item_id": item_id, "topic": topic, "account_id": account_id,
        "project_id": job.project_id or job.payload.get("project_id"),
    }, parent=job, account_id=account_id,
       project_id=job.project_id or job.payload.get("project_id"),
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "item_id": item_id, "topic": topic})


def ideate(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    account_id = job.payload.get("account_id") or job.account_id
    target = int(job.payload.get("target_posts") or 1)

    # ----- v5.9.5 DEMAND GOVERNOR RE-CHECK (DEC-021) -----
    # The tick that spawned this job may be stale by the time it is claimed
    # (queue delay, restarts). Re-verify unmet demand BEFORE the CEO gate or
    # any strategy-LLM spend; complete as a no-op if the quota is already met.
    if sb and account_id:
        from ..departments.portfolio import (_produced_today, _count_inflight,
                                             POSTS_PER_DAY_DEFAULT)
        acct0 = load_account(sb, account_id) or {}
        quota = int(acct0.get("posts_per_day") or POSTS_PER_DAY_DEFAULT)
        produced = _produced_today(sb, account_id)
        inflight0 = _count_inflight(sb, account_id)
        need = max(0, quota - produced - inflight0)
        if need <= 0:
            bus.agent("strategist", f"quota already met at claim time "
                                    f"({produced} produced + {inflight0} in-flight ≥ {quota}) — ideation no-op",
                      "info", "ideate_noop", job_id=job.id)
            w.queue.complete(job, {"ok": True, "noop": "quota_met"})
            return
        target = min(target, need)

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
    # v5.11.5 REQ-TOPIC-DEDUPE: the picker reads scouted trends, which keep
    # returning the same headline day after day. That produced 5 drafts titled
    # "Black Spots Gone Instantly!" and 3 of "Can Salish do her skincare in 1
    # minute?" — each one a separate paid write, a separate grade, and a separate
    # item in the founder's approval queue for the SAME idea.
    topics = _drop_recent_duplicates(sb, account_id, topics)
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

    # v5.9.5: an empty/whitespace topic is unwritable — fail the board item
    # here with the reason and spawn NOTHING downstream, instead of letting
    # creative.write_script die with a "no topic" fatal (9 in 7 days).
    if not (topic or "").strip():
        if sb and item_id:
            try:
                from ..common import board_get as _bget
                board_patch(sb, item_id, status="failed")
                p = dict((_bget(sb, item_id) or {}).get("payload") or {})
                p["failed_reason"] = "empty_topic_at_plan"
                sb.table("board_items").update({"payload": p}).eq("id", item_id).execute()
            except Exception:
                pass
        bus.agent("strategist", "🛑 plan_one received an EMPTY topic — item failed, "
                                "no writer job spawned", "warn", "plan_empty_topic",
                  job_id=job.id, item_id=item_id)
        w.queue.complete(job, {"ok": False, "reason": "empty_topic"})
        return

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
            # v5.8.1 FIX: recent_trends() returns a prompt STRING — the old code
            # iterated its CHARACTERS, creating literal one-letter board topics
            # ("U", "C"). Use the structured title list instead, guarded.
            trends = _s.recent_trend_titles(n * 3, niche=niche) if hasattr(_s, "recent_trend_titles") else []
            if not isinstance(trends, list):
                trends = []
            niche_kw = niche.split() if niche else []
            # First pass: niche matches
            for t in trends:
                if len(topics) >= n: break
                title = t if isinstance(t, str) else (t.get("title") if isinstance(t, dict) else "")
                if not title or len(title.strip()) < 8: continue
                low = title.lower()
                if niche_kw and any(kw in low for kw in niche_kw) and low not in seen:
                    topics.append((angle_from_trend(title, niche)[:120], "trend")); seen.add(low)
            # Second pass: any trend (but if niche is set, skip generic AI ones)
            for t in trends:
                if len(topics) >= n: break
                title = t if isinstance(t, str) else (t.get("title") if isinstance(t, dict) else "")
                if not title or len(title.strip()) < 8: continue
                low = title.lower()
                if niche and niche not in ("ai","ai tools","ai_tools","tech") and _is_generic_ai(" " + low + " "):
                    continue  # skip generic AI topics if this isn't an AI account
                if low not in seen:
                    topics.append((angle_from_trend(title, niche)[:120], "trend")); seen.add(low)
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


TOPIC_DEDUPE_DAYS = int(os.environ.get("TOPIC_DEDUPE_DAYS", "14"))


def _norm_topic(t: str) -> str:
    """Loose match: case, punctuation and emoji should not defeat dedupe."""
    import re as _re
    return _re.sub(r"[^a-z0-9 ]+", "", (t or "").lower()).strip()[:120]


def recent_topics(sb, account_id, days: int = None) -> set:
    """Topics this account already has on the board within the window."""
    if sb is None:
        return set()
    days = days or TOPIC_DEDUPE_DAYS
    try:
        import datetime as _dt
        since = (_dt.datetime.utcnow() - _dt.timedelta(days=days)).isoformat() + "Z"
        q = (sb.table("board_items").select("topic")
             .gte("created_at", since).limit(500))
        if account_id:
            q = q.eq("account_id", str(account_id))
        rows = q.execute().data or []
        return {_norm_topic(r.get("topic") or "") for r in rows if r.get("topic")}
    except Exception:
        return set()


def _drop_recent_duplicates(sb, account_id, topics: list) -> list:
    """Filter (topic, bucket) pairs against the board AND against each other."""
    seen = recent_topics(sb, account_id)
    out = []
    for pair in topics or []:
        try:
            topic = pair[0]
        except Exception:
            continue
        key = _norm_topic(topic)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(pair)
    return out


# ------------------------------------------------- v5.11.8 REQ-SCOUT-TITLES

# Markers that a scraped title is somebody's PERSONAL post rather than a topic.
_BORROWED_MARKERS = (
    "with me", "get ready", "get unready", "grwm", "my", "i", "im",
    "vlog", "day in the life", "come with", "lets", "watch me",
    "storytime", "who else", "she", "he", "her", "his",
)


def _looks_borrowed(title: str) -> bool:
    """True when a title reads as another creator's caption, not a subject.

    Word-boundary matching matters: a naive substring test flagged
    "7 AI Pet Gadgets That Save Time" because "i " occurs inside "ai ".
    """
    import re as _re
    t = (title or "").lower().strip()
    if not t:
        return False
    if any(ord(ch) > 0x2100 for ch in t):        # emoji-heavy captions
        return True
    if t.endswith("?") or "!" in t:
        return True
    for m in _BORROWED_MARKERS:
        if _re.search(r"\b" + _re.escape(m.strip()) + r"\b", t):
            return True
    return False


def _strip_personal(title: str) -> str:
    """Deterministic fallback — turn a caption into a subject phrase."""
    import re as _re
    t = _re.sub(r"[^\w\s\-]", " ", title or "")          # drop emoji/punctuation
    # Strip creator-voice scaffolding, question framing and leading proper names.
    t = _re.sub(r"\b(get (un)?ready with me|grwm|come with me|day in the life|"
                r"watch me|storytime|vlog|with me|who else has|"
                r"my|im|lets?|she|he|her|his|do|does|can)\b", " ", t, flags=_re.I)
    t = _re.sub(r"\bi\b", " ", t)                       # bare "I", never "ai"
    t = _re.sub(r"^\s*[A-Z][a-z]+\b(?=\s)", " ", t)      # leading proper name
    t = _re.sub(r"\b(a|an|the|very|in|the)\b\s*$", "", t, flags=_re.I)
    t = _re.sub(r"\s+", " ", t).strip()
    return t[:90]


def angle_from_trend(title: str, niche: str = "") -> str:
    """Convert a scraped trend title into an ORIGINAL angle.

    The scout reads public trend feeds, and the picker was using those titles
    VERBATIM as topics — so the board carried "Can Salish do her skincare in 1
    minute?" and "Get unready with me in the Bahamas!", which are other
    creators' captions naming other creators. The founder's own rule is clone
    the PATTERN, not the post.

    Free-model rewrite when available; deterministic subject extraction when not.
    Never raises — a bad angle must not stop planning.
    """
    raw = (title or "").strip()
    if not raw:
        return raw
    if not _looks_borrowed(raw):
        return raw                                   # already a topic, leave it
    try:
        from agentcore.council import free_chat
        out, _cost, _label = free_chat(
            "Rewrite this social post caption into a NEUTRAL content topic.\n"
            f"CAPTION: {raw[:180]}\n"
            f"NICHE: {niche or 'general'}\n\n"
            "Rules: describe the SUBJECT, not the creator. No names, no first "
            "person, no emoji, no question marks. 4-10 words. Return ONLY the "
            "topic line, nothing else.",
            max_tokens=40)
        cand = (out or "").strip().strip('"').splitlines()[0].strip()
        if 8 <= len(cand) <= 120 and not _looks_borrowed(cand):
            return cand
    except Exception:
        pass
    stripped = _strip_personal(raw)
    if len(stripped) < 8:
        return (niche or "daily tips").strip() + " routine that actually works"
    return stripped
