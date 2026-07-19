"""architect.py v4.1 — Account Architect agent.
Respects pause/resume: SKIPS accounts whose project OR account is paused.
Loads founder memory/guidance so brand docs reflect the user's notes.
"""
from . import config, ledger, events, llm, memory
import json, textwrap

DOC_TYPES = ["business_plan", "brand_guidelines", "tone_guide", "visual_rules", "content_rules"]

PROMPT = """You are a senior social-media brand architect for AI-generated faceless accounts.
You are creating a complete brand dossier for ONE specific account inside a multi-brand portfolio.
Write SHARP, CONCRETE, usable documents — no fluff, no corporate jargon.

Project niche: {niche}
Account name: {name}
Handle: {handle}
Target platforms: {platforms}
Account angle: {angle}
Daily budget: ${budget}

=== FOUNDER NOTES / PAST FEEDBACK (OBEY THESE) ===
{mem}

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
    accounts = _pending(limit)
    processed = 0
    for acc in accounts:
        # PAUSE CHECK — skip paused accounts/projects
        if acc.get("paused"):
            continue
        # Also check parent project paused state
        try:
            proj = _get_project(acc["project_id"])
            if proj and proj.get("paused"):
                continue
        except Exception:
            pass
        try:
            _set_status(acc["id"], "architecting")
            events.emit("architect", f"Laying foundation for @{acc['handle']} ({acc['name']})…",
                        "info", "architect_start", item_id=None)
            mem = memory.context_block(account_id=acc["id"], project_id=acc["project_id"])
            docs = _generate_docs(acc, mem)
            _save_docs(acc["id"], docs)
            _set_status(acc["id"], "strategizing")
            memory.add(account_id=acc["id"], role="architect",
                      content=f"Brand kit written: business_plan, brand_guidelines, tone_guide, visual_rules, content_rules.",
                      metadata={"handle": acc["handle"]})
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
    res = (sb.table("project_accounts")
           .select("*")
           .eq("status", "needs_setup")
           .eq("paused", False)
           .limit(50).execute())
    out = []
    for r in res.data or []:
        try:
            pj = sb.table("projects").select("paused").eq("id", r["project_id"]).single().execute().data
            if pj and pj.get("paused"):
                continue
        except Exception:
            pass
        out.append(r)
        if len(out) >= limit: break
    return out


def _get_project(pid):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    return sb.table("projects").select("paused,name").eq("id", pid).single().execute().data


def _set_status(acc_id, status):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    sb.table("project_accounts").update({"status": status}).eq("id", acc_id).execute()


def _generate_docs(acc, mem: str) -> dict:
    niche = acc.get("niche") or "AI tools"
    name = acc.get("name") or "Account"
    handle = acc.get("handle") or "account"
    plats = acc.get("platforms") or ["instagram","tiktok"]
    platforms = ", ".join(plats) if isinstance(plats, list) else str(plats)
    angle = ((acc.get("platforms_config") or {}).get("angle")
             or (acc.get("config") or {}).get("angle")
             or f"{niche} tips, daily")
    budget = acc.get("daily_budget_usd") or 0.5
    prompt = PROMPT.format(niche=niche, name=name, handle=handle, platforms=platforms,
                           angle=angle, budget=budget, mem=mem[:3000])

    docs = None
    if llm.ready() and ledger.budget_ok(0.04):
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=3000)
            ledger.record("architect", model=mlabel, cost_usd=cost, detail=f"@{handle}")
            docs = json.loads(text[text.find("{"): text.rfind("}")+1])
        except Exception as e:
            ledger.record("architect", ok=False, detail=str(e)[:200])

    if not docs:
        docs = _fallback_docs(acc)

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


# ---------- FALLBACK ----------
def _fallback_docs(acc) -> dict:
    niche = (acc.get("niche") or "ai_tools").replace("_", " ")
    name = acc.get("name") or "Account"
    handle = acc.get("handle") or "account"
    platforms = ", ".join(acc.get("platforms") or ["Instagram","TikTok"])
    angle = ((acc.get("platforms_config") or {}).get("angle") or f"{niche} tips")

    palette = _niche_palette(acc.get("niche","ai_tools"))

    return {
      "business_plan": textwrap.dedent(f"""\
# 📘 Business Plan — @{handle}

**Account:** {name}
**Niche:** {niche}
**Angle:** {angle}
**Platforms:** {platforms}

## Mission
Deliver one concrete, actionable tip per post for {niche} beginners. No fluff, no hype. Clone the ANGLE of viral posts (never repost).

## Target Audience
- 18–34 year olds · English-speaking
- Wants fast answers · overwhelmed by noise
- Pain point: 100 tutorials but nothing specific

## Monetization Stack
| Layer | % |
|---|---|
| Affiliates (tools we actually use) | 40% |
| Creator fund ad revenue | 30% |
| Digital product (toolkit/checklist) | 20% |
| Sponsorships (after 10k followers) | 10% |

## 90-Day Goal
1,000 followers, first affiliate payout, 200 email subs.

## 3 Competitors to Study
- Top 3 faceless {niche} accounts with 50k+ followers. Study their HOOKS + SHOT LIST (never repost).

## Risk to Avoid
Straight reposting = banned. Clone the ANGLE, not the content.
"""),
      "brand_guidelines": textwrap.dedent(f"""\
# 🎨 Brand Guidelines — @{handle}

## One-line promise
One {niche} win per day — in under 60 seconds.

## Archetype
The Sharp Friend — smarter than average, never condescending.

## Brand Values
1. **Specificity** — show the exact button / exact prompt / exact link
2. **Honesty** — say when a tool sucks, don't shill
3. **Speed** — value in <8s, CTA by second 40

## Visual Signature
- Palette: {palette}
- Emoji stamp: ⚡ on every corner badge
- Sign-off: "That's it — one move a day."
"""),
      "tone_guide": textwrap.dedent(f"""\
# 🗣️ Tone Guide — @{handle}

## Voice
Direct · Playful · Specific

## Do
1. Open with a pattern-interrupt hook (<=8 words)
2. Use "you" 2x more than "I"
3. Keep sentences under 12 words
4. End every post with a SINGLE verb CTA
5. Lowercase captions; no hashtags stacked in caption

## Don't
- "Hey guys" / "what's up" / "in today's video"
- "Game changer" / "revolutionary" / "you won't believe"
- All-caps spam
- Long disclaimers
- Fake urgency ("last chance!")

## Example Hooks
- "stop scrolling."
- "your browser has a free ai."
- "this one setting doubled my output."

## Example CTAs
- "follow for one move a day."
- "save this before it's gone."
- "comment 'TOOL' and i'll send the link."
"""),
      "visual_rules": textwrap.dedent(f"""\
# 🎬 Visual Rules — @{handle}

## Palette
{palette}

## Dominant Style
**{_niche_style(acc.get("niche","ai_tools"))}** — rotate to a secondary style once per week.

## Thumbnail Pattern
- 1-3 word hook in top third (bold, brand accent color)
- Circular reaction sticker top-right
- Darkened bottom third for subtitle safety
- Progress dots across top (TikTok segment style)

## Caption Style
- Lowercase, 1-3 lines max
- 1 emoji per line
- CTA on last line only

## B-Roll Preference
Phone screen closeups, UI zooms, hand-held phone, keyboard typing, isometric 3D icons. No generic stock wallpapers.
"""),
      "content_rules": textwrap.dedent(f"""\
# 📐 Content Rules — @{handle}

## Cadence
- TikTok/IG Reels: 1 per day
- YouTube Shorts: cross-post
- X/Twitter: 1 thread per week

## Hook Patterns That Work
1. Two-word stop: "stop scrolling."
2. Bold secret: "no one talks about this."
3. Specific number: "3 tools that replaced my job."
4. Direct question: "you know what your browser hides?"
5. Anti-hook: "this isn't for everyone."

## Content Pillars
1. ⚡ Quick tip (<30s — one tool / one trick)
2. 🔍 Deep dive (60s — "how to actually use X")
3. ❌ Don't do this (mistake + fix)
4. 📊 Results (proof / earnings / metrics)

## Hashtags
| Tier | Tags |
|---|---|
| Big | #ai #tech #tools #chatgpt #productivity |
| Medium | #aitools #techtok #learnai #aitips #sidehustle |
| Niche | #aiupdates #aitoolsdaily #automation |

## Forbidden
- "get rich quick" · fake screenshots · straight reposts · crypto/NFT shilling · overclaiming

## CTA Rotation (every 3 posts)
1. "follow for one move a day."
2. "save this."
3. "comment 'LINK' and i'll send it."
"""),
    }


def _niche_palette(slug: str) -> str:
    m = {
      "ai_tools":"Primary: #0f172a (navy) · Accent: #22d3ee (cyan) · Pop: #ef4444 · Neutrals: #fafaf9, #1e293b",
      "fitness":"Primary: #0c0a09 · Accent: #f97316 (orange) · Pop: #dc2626 · Neutrals: #f5f5f4, #292524",
      "cooking":"Primary: #422006 · Accent: #f59e0b (amber) · Pop: #ef4444 · Neutrals: #fef3c7, #1c1917",
      "skincare":"Primary: #fce7f3 · Accent: #ec4899 (pink) · Pop: #8b5cf6 · Neutrals: #fdf2f8, #500724",
      "men_style":"Primary: #1c1917 · Accent: #a3a3a3 (steel) · Pop: #d97706 · Neutrals: #fafaf9, #292524",
      "motivation":"Primary: #000000 · Accent: #fbbf24 (gold) · Pop: #dc2626 · Neutrals: #18181b, #fafaf9",
      "luxury":"Primary: #0a0a0a · Accent: #d4af37 (gold) · Pop: #b91c1c · Neutrals: #171717, #f5f5f4",
    }
    return m.get(slug, "Primary: #0f172a · Accent: #22d3ee (cyan) · Pop: #ef4444 · Neutrals: #fafaf9, #1e293b")


def _niche_style(slug: str) -> str:
    m = {"fitness":"cinematic-stock","cooking":"editorial-pop","skincare":"editorial-pop","men_style":"editorial-pop",
         "motivation":"cinematic-stock","luxury":"cinematic-stock","pets":"meme-energetic","home_hacks":"editorial-pop",
         "travel":"nature-calm","gaming":"retro-wave","psychology":"cinematic-stock","dating":"meme-energetic"}
    return m.get(slug, "tech-noir")


def _fallback_doc(dt: str, acc) -> str:
    return _fallback_docs(acc).get(dt, f"# {dt}\n\nTo be written.")
