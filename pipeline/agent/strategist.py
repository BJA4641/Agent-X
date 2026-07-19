"""strategist.py — Content Strategist agent.
When an account hits status='strategizing' (Architect finished), this agent:
  1. Reads the account's brand/tone/visual/content rules
  2. Plans 10 initial posts (reels by default) with full hook, script, caption,
     hashtags, visual_prompt, metadata
  3. Stores them in account_posts with status='planned'
  4. Flips the account to status='ready'
"""
from . import config, ledger, events, llm
import json, textwrap

PROMPT = """You are a senior short-form content strategist for a faceless social media account.
Given the brand, tone, visual, and content rules below, plan TEN kickoff posts for the first
two weeks of this account. Mix content pillars. Hooks must be 10 words or fewer. Scripts
should be 4-5 beats of <=12 words each. Captions should be lowercase, casual, 2-3 lines.

=== BUSINESS PLAN ===
{business_plan}

=== BRAND GUIDELINES ===
{brand_guidelines}

=== TONE GUIDE ===
{tone_guide}

=== VISUAL RULES ===
{visual_rules}

=== CONTENT RULES ===
{content_rules}

Return STRICT JSON:
{{"posts": [
  {{
    "post_type": "reel"|"carousel"|"image"|"short",
    "title": string (one-line headline, internal),
    "hook": string (<=10 words — first spoken line AND poster word),
    "script": string (full voiceover script, spoken naturally, 25-40 seconds),
    "caption": string (Instagram/TikTok caption — lowercase, emoji-sparse, one CTA),
    "visual_prompt": string (cinematic 9:16 image description for AI — no text),
    "hashtags": [string x10 — mix big/medium/niche WITHOUT # prefix],
    "duration_seconds": int (25-45 for reels),
    "pillar": string (quick_tip|deep_dive|mistake|results)
  }} x10
]}}"""


def run_for_account(account_id: str, n: int = 10) -> int:
    """Run for one specific account. Returns number of posts created."""
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    acc = sb.table("project_accounts").select("*").eq("id", account_id).single().execute().data
    if not acc: return 0
    docs = {r["doc_type"]: r["content"]
            for r in (sb.table("account_documents").select("doc_type,content").eq("account_id", account_id).execute().data or [])}
    if len(docs) < 5:
        events.emit("strategist", f"Skipping @{acc['handle']} — missing brand docs.", "warn", "skip")
        return 0
    events.emit("strategist", f"Planning {n} kickoff posts for @{acc['handle']}…", "info", "strategy_start")
    posts = _generate_posts(acc, docs, n)
    if not posts:
        posts = _fallback_posts(acc, n)
    _save_posts(sb, acc, posts)
    sb.table("project_accounts").update({"status": "ready"}).eq("id", account_id).execute()
    events.emit("strategist", f"{len(posts)} posts planned for @{acc['handle']} → account ready.",
                "success", "strategy_done")
    return len(posts)


def run(limit: int = 1) -> int:
    """Process up to `limit` accounts that are waiting for strategy."""
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    accs = sb.table("project_accounts").select("id,name,handle,niche,platforms").eq("status", "strategizing").limit(limit).execute().data or []
    total = 0
    for acc in accs:
        try:
            total += run_for_account(acc["id"])
        except Exception as e:
            events.error("strategist", f"Strategist failed for @{acc['handle']}: {str(e)[:200]}")
            ledger.record("strategist", ok=False, detail=str(e)[:300])
    return total


def _generate_posts(acc, docs, n):
    prompt = PROMPT.format(
        business_plan=docs.get("business_plan", ""),
        brand_guidelines=docs.get("brand_guidelines", ""),
        tone_guide=docs.get("tone_guide", ""),
        visual_rules=docs.get("visual_rules", ""),
        content_rules=docs.get("content_rules", ""))
    if llm.ready() and ledger.budget_ok(0.05):
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=3500)
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
            "post_type": p.get("post_type", "reel"),
            "title": p.get("title", p.get("hook", "Untitled"))[:120],
            "hook": (p.get("hook") or "")[:120],
            "script": p.get("script") or "",
            "caption": p.get("caption") or "",
            "visual_prompt": p.get("visual_prompt") or "",
            "hashtags": [h.lstrip("#") for h in (p.get("hashtags") or [])],
            "duration_seconds": int(p.get("duration_seconds") or 30),
            "status": "planned",
            "created_by_agent": "strategist",
            "metadata": {"pillar": p.get("pillar", "quick_tip")}
        })
    if rows:
        sb.table("account_posts").insert(rows).execute()


# ---------- Fallback (no LLM) ----------
def _fallback_posts(acc, n):
    niche = (acc.get("niche") or "ai tools").replace("_", " ")
    hooks = [
        "stop scrolling.", "you need to see this.", "everyone misses this.",
        "this changed everything.", "i was today years old.", "the secret is out.",
        "this is illegal in 3 countries.", "nobody tells you this.",
        "delete this app.", "use this instead."
    ]
    posts = []
    pillars = ["quick_tip", "deep_dive", "mistake", "results"]
    for i in range(n):
        hook = hooks[i % len(hooks)]
        posts.append({
            "post_type": "reel",
            "title": f"{niche} tip #{i+1}",
            "hook": hook,
            "script": f"{hook} Here is one {niche} trick that saves me hours every week. Most people do it the long way. There is a faster method hiding in plain sight. That is it, one move a day.",
            "caption": f"save this for later · one {niche} move a day",
            "visual_prompt": f"cinematic dark vertical 9:16, close up of a phone with a {niche} app glowing, neon cyan accents, tech-noir, no text",
            "hashtags": ["ai","tech","tools","productivity","aitools","techtok","learnai","aitips","sidehustle","aiupdates"],
            "duration_seconds": 30,
            "pillar": pillars[i % 4],
        })
    return posts
