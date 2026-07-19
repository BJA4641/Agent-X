"""strategist.py v4.3 — Content Strategist agent.
Respects pause/resume; injects trends + founder memory + research into planning.
"""
from . import config, ledger, events, llm
import json, textwrap
try:
    from . import memory
except Exception as _e:
    print(f"[strategist] WARNING: memory import failed ({_e}); using no-op stub.")
    from . import _memstub
    memory = _memstub.MemoryStub()

PROMPT = """You are a senior short-form content strategist for a faceless social media account.
Plan TEN kickoff posts for the first two weeks. Hooks ≤10 words. Scripts should be tight,
25-40 seconds, opinionated, specific. Captions lowercase, casual, 2-3 lines, one CTA.

=== EXECUTIVE SUMMARY ===
{executive_summary}

=== BRAND IDENTITY (voice, audience, persona, DO/DON'T, hooks, CTAs) ===
{brand_identity}

=== VISUAL IDENTITY (palette, fonts, shot style, thumbnail formula) ===
{visual_identity}

=== MARKETING STRATEGY (funnel, virality, cross-platform) ===
{marketing_strategy}

=== CONTENT RULES (pillars, hook patterns, forbidden phrases, CTA rotation) ===
{content_rules}

=== HASHTAGS & SEO ===
{hashtags_seo}

=== PRODUCTION SOP ===
{production_sop}

=== INSTAGRAM PLAYBOOK ===
{instagram_playbook}

=== TIKTOK PLAYBOOK (hook formulas, retention, trends) ===
{tiktok_playbook}

=== CONTENT CALENDAR (weekly rhythm, themes) ===
{content_calendar}

=== REVENUE MODEL ===
{revenue_model}

=== VISION / MISSION ===
{vision_mission}

=== YOUTUBE PLAYBOOK ===
{youtube_playbook}

=== FOUNDER NOTES / FEEDBACK (OBEY THESE EXPLICITLY) ===
{mem}

=== CURRENT VIRAL TREND PATTERNS (clone the ANGLE, structure, tone, pacing — never the words) ===
{trends}

Return STRICT JSON:
{{"posts": [
  {{
    "post_type": "reel"|"carousel"|"image"|"short",
    "title": string (one-line, internal),
    "hook": string (<=10 words — first spoken line AND poster word — MATCH one of the current trend patterns above),
    "script": string (full voiceover, 25-40 seconds, spoken naturally, snappy, creator voice, sentences <=12 words, pattern-interrupt opening),
    "caption": string (lowercase, 2-3 lines, 1 emoji per line, single CTA on last line),
    "visual_prompt": string (cinematic 9:16 image — specific shot: phone closeup / UI mockup / over-shoulder / isometric / B-roll — NO text),
    "hashtags": [string x10 — mix big/medium/niche WITHOUT #],
    "duration_seconds": int (25-45 for reels),
    "pillar": string (quick_tip|deep_dive|mistake|results),
    "trend_pattern": string (which of the current patterns you cloned, e.g. "pattern_interrupt" or "specific_number")
  }}
] x10}}"""


def run_for_account(account_id: str, n: int = 10) -> int:
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    acc = sb.table("project_accounts").select("*").eq("id", account_id).single().execute().data
    if not acc: return 0
    # PAUSE CHECK — account level
    if acc.get("paused"):
        return 0
    # PAUSE CHECK — project level
    try:
        pj = sb.table("projects").select("paused").eq("id", acc["project_id"]).single().execute().data
        if pj and pj.get("paused"):
            return 0
    except Exception:
        pass
    docs = {r["doc_type"]: r["content"]
            for r in (sb.table("account_documents").select("doc_type,content").eq("account_id", account_id).execute().data or [])}
    # Architect writes 13 docs now; we need at least executive_summary + brand_identity
    need = ("executive_summary" in docs) or ("business_plan" in docs)
    if not need:
        events.emit("strategist", f"Skipping @{acc['handle']} — architect hasn't finished brand docs yet.", "warn", "skip")
        return 0

    mem = memory.context_block(account_id=account_id, project_id=acc["project_id"])
    try:
        from . import scout
        trends = scout.recent_trends(5)
    except Exception:
        trends = "(trend scout unavailable — use pattern_interrupt + specific_number hooks)"

    events.emit("strategist", f"Planning {n} kickoff posts for @{acc['handle']} (trend-aware)…", "info", "strategy_start")
    posts = _generate_posts(acc, docs, n, mem, trends)
    if not posts:
        posts = _fallback_posts(acc, n)
    _save_posts(sb, acc, posts)
    sb.table("project_accounts").update({"status": "ready"}).eq("id", account_id).execute()
    memory.add(account_id=account_id, role="strategist",
              content=f"Planned {len(posts)} kickoff posts (trend-aware).",
              metadata={"count": len(posts)})
    events.emit("strategist", f"{len(posts)} posts planned for @{acc['handle']} → account ready.",
                "success", "strategy_done")
    return len(posts)


def run(limit: int = 1) -> int:
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    res = (sb.table("project_accounts")
           .select("id,name,handle,project_id,paused")
           .eq("status", "strategizing")
           .eq("paused", False)
           .limit(50).execute())
    accs = []
    for a in res.data or []:
        try:
            pj = sb.table("projects").select("paused").eq("id", a["project_id"]).single().execute().data
            if pj and pj.get("paused"): continue
        except Exception:
            pass
        accs.append(a)
        if len(accs) >= limit: break
    total = 0
    for acc in accs[:limit]:
        try:
            total += run_for_account(acc["id"])
        except Exception as e:
            events.error("strategist", f"Strategist failed for @{acc['handle']}: {str(e)[:200]}")
            ledger.record("strategist", ok=False, detail=str(e)[:300])
    return total


def _generate_posts(acc, docs, n, mem, trends):
    # Support both the old 5-doc aliases AND the new 13-doc set
    prompt = PROMPT.format(
        executive_summary=docs.get("executive_summary", docs.get("business_plan",""))[:2500],
        brand_identity=docs.get("brand_identity", docs.get("brand_guidelines",""))[:2000],
        visual_identity=docs.get("visual_identity", docs.get("visual_rules",""))[:1500],
        marketing_strategy=docs.get("marketing_strategy","")[:1500],
        content_rules=docs.get("content_rules","")[:1500],
        hashtags_seo=docs.get("hashtags_seo","")[:1000],
        production_sop=docs.get("production_sop","")[:1200],
        instagram_playbook=docs.get("instagram_playbook","")[:1200],
        tiktok_playbook=docs.get("tiktok_playbook","")[:1200],
        content_calendar=docs.get("content_calendar","")[:1000],
        revenue_model=docs.get("revenue_model","")[:800],
        vision_mission=docs.get("vision_mission","")[:800],
        youtube_playbook=docs.get("youtube_playbook","")[:1000],
        mem=mem[:2000],
        trends=trends[:2000])
    if llm.ready() and ledger.budget_ok(0.06):
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=4000)
            ledger.record("strategist", model=mlabel, cost_usd=cost, detail=f"@{acc['handle']}")
            parsed = json.loads(text[text.find("{"): text.rfind("}")+1])
            posts = parsed.get("posts", [])
            if isinstance(posts, list) and len(posts) >= 3:
                return posts[:n]
        except Exception as e:
            ledger.record("strategist", ok=False, detail=str(e)[:200])
    return None


def _save_posts(sb, acc, posts):
    rows = []
    for p in posts:
        rows.append({
            "account_id": acc["id"],
            "post_type": p.get("post_type","reel"),
            "title": p.get("title", p.get("hook","Untitled"))[:120],
            "hook": (p.get("hook") or "")[:120],
            "script": p.get("script") or "",
            "caption": p.get("caption") or "",
            "visual_prompt": p.get("visual_prompt") or "",
            "hashtags": [h.lstrip("#") for h in (p.get("hashtags") or [])],
            "duration_seconds": int(p.get("duration_seconds") or 30),
            "status": "planned",
            "created_by_agent": "strategist",
            "metadata": {
                "pillar": p.get("pillar","quick_tip"),
                "trend_pattern": p.get("trend_pattern","pattern_interrupt"),
            },
        })
    if rows:
        sb.table("account_posts").insert(rows).execute()


# ---------- Fallback ----------
def _fallback_posts(acc, n):
    niche = (acc.get("niche") or "ai tools").replace("_"," ")
    angle = ((acc.get("platforms_config") or {}).get("angle")
             or f"one {niche} win per day")
    # Trend-pattern-matching fallback hooks
    pattern_hooks = [
      ("pattern_interrupt", "stop scrolling."),
      ("specific_number", f"3 {niche} hacks that work."),
      ("secret_reveal", "nobody talks about this."),
      ("contrarian_truth", f"most {niche} advice is wrong."),
      ("relatable_pain", "i wasted months on this."),
      ("demo_showcase", "just press this button."),
      ("mistake_warning", "stop doing this."),
      ("result_first", f"$300/day from this trick."),
      ("pattern_interrupt", "wait until the end."),
      ("specific_number", "the 7 second trick."),
    ]
    posts = []
    for i in range(n):
        pat, hook = pattern_hooks[i % len(pattern_hooks)]
        posts.append({
            "post_type": "reel",
            "title": f"{niche} {pat} #{i+1}",
            "hook": hook,
            "script": (f"{hook} Here is one {niche} trick most people miss. It takes 30 seconds and saves hours. "
                       f"Everybody does it the hard way. The trick is hiding in plain sight. {angle}. follow for one move a day."),
            "caption": f"save this for later\none {niche} move a day 💡\nfollow for more",
            "visual_prompt": f"cinematic dark vertical 9:16, close-up phone screen with {niche} app glowing, neon cyan accent, tech-noir, no text",
            "hashtags": ["ai","tech","tools","productivity","aitools","techtok","learnai","aitips","sidehustle","viral"],
            "duration_seconds": 30,
            "pillar": "quick_tip",
            "trend_pattern": pat,
        })
    return posts
