"""architect.py — the Account Architect agent.
When a new account is created with status='needs_setup', this agent:
  1. Writes a markdown BUSINESS PLAN
  2. Writes BRAND GUIDELINES (name, audience, promise, archetype)
  3. Writes TONE GUIDE (voice, do/don't, example lines)
  4. Writes VISUAL RULES (palette, style, thumbnail pattern)
  5. Writes CONTENT RULES (posting cadence, hashtags, forbidden patterns)

All five documents are stored in account_documents. The agent then
flips account status to 'strategizing' so the Content Strategist can
plan the first batch of posts.
"""
from . import config, ledger, events, board, llm
import json, time, textwrap

DOC_TYPES = ["business_plan", "brand_guidelines", "tone_guide", "visual_rules", "content_rules"]

PROMPT = """You are a senior social-media brand architect for AI-generated faceless accounts.
You are creating a complete brand dossier for ONE specific account inside a multi-brand
portfolio. Write SHARP, CONCRETE, usable documents — no fluff, no corporate jargon.

Project niche: {niche}
Account name: {name}
Handle: {handle}
Target platforms: {platforms}

Return STRICT JSON with keys exactly:
{{
  "business_plan": "# [markdown string]\\n\\nSections: mission, target-audience (age/gender/pain point), monetization (exact layers: affiliates / ad revenue / digital / sponsorships with % target), 90-day goal, 3 competitors to study, risk to avoid",
  "brand_guidelines": "# [markdown string]\\n\\nSections: one-line promise, archetype (The X who Y), 3 brand values, personality adjectives, visual signature (colors / pattern / emoji), catchphrase sign-off",
  "tone_guide": "# [markdown string]\\n\\nSections: voice (3 adjectives), do-list (5 specific things we sound like), don't-list (5 forbidden phrases/ticks), 3 example opening hooks in our voice, 3 example CTAs in our voice",
  "visual_rules": "# [markdown string]\\n\\nSections: palette (hex codes, 3 colors + neutrals), dominant visual style (pick one: tech-noir / editorial-pop / cinematic-stock / clay-3d / meme-energetic / glass-minimal / retro-wave / nature-calm), thumbnail pattern, caption style (lowercase? emojis? length), b-roll preference",
  "content_rules": "# [markdown string]\\n\\nSections: posting cadence per platform, hook patterns that work (5 examples), content pillars (3-4 with examples), hashtags (3 tiers: big/medium/niche x5 each), forbidden (what we never do), CTA rotation"
}}
Every value must be a COMPLETE markdown document string. Use emojis and bold to make them scannable."""


def run(limit: int = 1) -> int:
    """Process up to `limit` accounts that need setup. Returns number processed."""
    accounts = _pending(limit)
    processed = 0
    for acc in accounts:
        try:
            _set_status(acc["id"], "architecting")
            events.emit("architect", f"Laying foundation for @{acc['handle']} ({acc['name']})…",
                        "info", "architect_start", item_id=None)
            docs = _generate_docs(acc)
            _save_docs(acc["id"], docs)
            _set_status(acc["id"], "strategizing")
            events.emit("architect", f"Brand kit complete for @{acc['handle']} — 5 documents written. Handing to strategist.",
                        "success", "architect_done")
            processed += 1
        except Exception as e:
            _set_status(acc["id"], "needs_setup")
            events.error("architect", f"Architect failed for @{acc['handle']}: {str(e)[:200]}")
            ledger.record("architect", ok=False, detail=str(e)[:300])
    return processed


def _pending(limit: int):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    res = sb.table("project_accounts").select("*").eq("status", "needs_setup").limit(limit).execute()
    return res.data or []


def _set_status(acc_id, status):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    sb.table("project_accounts").update({"status": status}).eq("id", acc_id).execute()


def _generate_docs(acc) -> dict:
    niche = acc.get("niche") or "AI tools"
    name = acc.get("name") or "Account"
    handle = acc.get("handle") or "account"
    plats = acc.get("platforms") or ["instagram","tiktok"]
    platforms = ", ".join(plats) if isinstance(plats, list) else str(plats)
    prompt = PROMPT.format(niche=niche, name=name, handle=handle, platforms=platforms)

    docs = None
    if llm.ready() and ledger.budget_ok(0.03):
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=2500)
            ledger.record("architect", model=mlabel, cost_usd=cost, detail=f"@{handle}")
            docs = json.loads(text[text.find("{"): text.rfind("}")+1])
        except Exception as e:
            ledger.record("architect", ok=False, detail=str(e)[:200])

    if not docs:
        docs = _fallback_docs(acc)

    # Validate all 5 keys present
    for dt in DOC_TYPES:
        if dt not in docs or not isinstance(docs[dt], str) or len(docs[dt]) < 50:
            docs[dt] = _fallback_doc(dt, acc)
    return docs


def _save_docs(acc_id, docs: dict):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    for dt in DOC_TYPES:
        sb.table("account_documents").upsert({
            "account_id": acc_id,
            "doc_type": dt,
            "content": docs[dt],
            "agent": "architect",
        }, on_conflict="account_id,doc_type").execute()


# ---------- FALLBACK (no LLM keys — still produces usable dossiers) ----------
def _fallback_docs(acc) -> dict:
    niche = (acc.get("niche") or "ai_tools").replace("_", " ")
    name = acc.get("name") or "Account"
    handle = acc.get("handle") or "account"
    platforms = ", ".join(acc.get("platforms") or ["Instagram","TikTok"])

    return {
      "business_plan": textwrap.dedent(f"""\
# 📘 Business Plan — @{handle}

**Account:** {name}
**Niche:** {niche}
**Platforms:** {platforms}

## Mission
Deliver one concrete, actionable tip per post for {niche} beginners. No fluff, no hype.

## Target Audience
- 18–34 year olds
- English-speaking
- Looking to save time / make money / learn fast
- Pain: overwhelmed by noise, wants one specific answer

## Monetization Stack
| Layer | % of revenue |
|---|---|
| Affiliate links (tools we recommend) | 40% |
| Creator Fund ad revenue (YT / TikTok / IG bonuses) | 30% |
| Digital product (e.g. toolkit / checklist) | 20% |
| Sponsorships (once >10k followers) | 10% |

## 90-Day Goal
1,000 followers across platforms, first affiliate payout, email list of 200.

## 3 Competitors to Watch
- Top 3 accounts in the niche with 50k+ followers

## Risk to Avoid
Reposting others' content without original angle — leads to demonetization / bans.
"""),
      "brand_guidelines": textwrap.dedent(f"""\
# 🎨 Brand Guidelines — @{handle}

## One-line promise
One {niche} win per day — in under 60 seconds.

## Archetype
The Sharp Friend — smarter than the average creator but never condescending.

## Brand Values
1. **Specificity** — show the exact button / exact prompt / exact link
2. **Honesty** — say when a tool sucks, don't shill
3. **Speed** — deliver value in <10 seconds, CTA by second 45

## Visual Signature
- Palette: deep navy (#0f172a) + cyan accent (#22d3ee) + cream (#fafaf9)
- Emoji: ⚡ (default stamp on every post corner)
- Catchphrase sign-off: "That's it — one move a day."
"""),
      "tone_guide": textwrap.dedent(f"""\
# 🗣️ Tone Guide — @{handle}

## Voice
- Direct (never hedges)
- Playful (small joke here and there)
- Specific (names, buttons, shortcuts, prices)

## Do
1. Open with the most surprising fact
2. Use "you" 2x more than "I"
3. Keep sentences under 12 words
4. End every post with a single verb CTA
5. Use lowercase captions for TikTok/IG, sentence case for YouTube

## Don't
- "Hey guys" / "what's up" openings
- "In today's video" / "let's talk about"
- All caps hooks (feels spammy)
- "Game changer" / "revolutionary"
- Long-winded disclaimers

## Example Hooks
- "stop scrolling."
- "your browser has a free ai you never opened."
- "this one setting doubled my output."

## Example CTAs
- "follow for one move a day."
- "save this before it gets taken down."
- "comment 'TOOL' and i'll send the link."
"""),
      "visual_rules": textwrap.dedent(f"""\
# 🎬 Visual Rules — @{handle}

## Palette
- Primary: #0f172a (deep navy)
- Accent:  #22d3ee (cyan)
- Pop:     #ef4444 (red, for STOP hooks)
- Neutrals: #fafaf9 (cream), #1e293b (slate)

## Dominant Style
**tech-noir** — dark background, neon cyan accents, phone / UI closeups. Rotate to
editorial-pop once a week for variety.

## Thumbnail Pattern
- Big 2-word hook in top third (red or cyan, bold)
- Circular reaction sticker in top-right corner
- Darkened bottom third for subtitles
- Progress dots across top like TikTok segments

## Caption Style
- Lowercase, 1-3 lines max
- 1 emoji per line
- CTA on last line only

## B-roll Preference
- iPhone screen recordings (fast zooms)
- App UI closeups
- Isometric 3D app icons
- Fast keyboard typing footage
"""),
      "content_rules": textwrap.dedent(f"""\
# 📐 Content Rules — @{handle}

## Cadence
- TikTok: 1 reel per day
- Instagram Reels: cross-post from TikTok
- YouTube Shorts: 3 per week
- Twitter/X: 1 thread per week

## Hook Patterns That Work
1. Two-word stop: "stop scrolling."
2. Bold secret: "no one talks about this."
3. Specific number: "3 tools that replaced my job."
4. Direct question: "you know what your browser hides?"
5. Anti-hook: "this isn't for everyone."

## Content Pillars
1. ⚡ Quick tips (under 30 seconds — one tool / one trick)
2. 🔍 Deep dives (60 seconds — "how to actually use X")
3. ❌ Don't do this (mistake + fix)
4. 📊 Results (proof / earnings / metrics)

## Hashtags
| Tier | Tags (5 each) |
|---|---|
| Big | #ai #tech #tools #chatgpt #productivity |
| Medium | #aitools #techtok #learnai #aitips #sidehustle |
| Niche | #aiupdates #aitoolsdaily #automation #aitool |

## Forbidden
- No "get rich quick"
- No fake screenshots
- No reposts of other creators
- No crypto/NFT shilling
- No overclaiming ("make $10k/day" etc.)

## CTA Rotation (rotate every 3 posts)
1. "follow for one move a day."
2. "save this."
3. "comment 'LINK' and i'll send it."
"""),
    }


def _fallback_doc(dt: str, acc) -> str:
    return _fallback_docs(acc).get(dt, f"# {dt}\n\nTo be written.")
