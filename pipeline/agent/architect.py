"""architect.py v4.2 — FULL Business Plan Generator.
Generates 13 documents per account covering everything the user asked for:

  • executive_summary   — Executive summary (business foundation)
  • vision_mission      — Vision, mission, goals (short/long term)
  • revenue_model       — Monetization, KPIs, growth roadmap
  • brand_identity      — Brand identity, positioning, persona, voice/tone
  • visual_identity     — Colors, typography, image/video style, thumbnail system
  • marketing_strategy  — Positioning, SWOT, funnel, organic/paid, community, virality
  • instagram_playbook  — IG feed/reels/stories/carousels, hashtags, posting times
  • tiktok_playbook     — TikTok hooks, retention, trends, hashtags, CTAs
  • youtube_playbook    — YT shorts/longform, titles, thumbnails, SEO, monetization
  • content_calendar    — Daily/weekly/monthly schedule, seasonal/holiday campaigns
  • content_rules       — Content pillars, hook patterns, forbidden patterns, CTA rotation
  • hashtags_seo        — Hashtag tiers, keyword list, SEO strategy
  • production_sop      — Standard operating procedure for making every post

All agents (brain, strategist, scout, grader) load these docs and must comply.
Respects pause/resume state and persistent user memory.
"""
import json, textwrap, traceback as _tb
from . import config, ledger, events, llm
# memory is a soft dependency — if it's missing from a stale deploy,
# fall back to no-ops instead of crashing the whole container on import.
try:
    from . import memory
except Exception as _e:
    print(f"[architect] WARNING: memory import failed ({_e}); using no-op stub.")
    _tb.print_exc()
    class _MemoryStub:
        @staticmethod
        def add(**kw): pass
        @staticmethod
        def recent(**kw): return []
        @staticmethod
        def context_block(**kw): return "No prior guidance yet."
        @staticmethod
        def load_grade_feedback(**kw): return ""
    memory = _MemoryStub()

DOC_TYPES = [
    "executive_summary", "vision_mission", "revenue_model",
    "brand_identity", "visual_identity", "marketing_strategy",
    "instagram_playbook", "tiktok_playbook", "youtube_playbook",
    "content_calendar", "content_rules", "hashtags_seo", "production_sop",
]
# Aliases kept for backwards compat with old code expecting 5 docs
DOC_ALIASES = {
    "business_plan":    "executive_summary",
    "brand_guidelines": "brand_identity",
    "tone_guide":       "brand_identity",
    "visual_rules":     "visual_identity",
}

ARCHITECT_PROMPT = """You are a WORLD-CLASS brand architect for faceless social media portfolios.
You are creating a COMPLETE business plan for ONE account in a 100-brand portfolio.
Every document must be SHARP, SPECIFIC, ACTIONABLE, and ready to hand to a content team.
NO FLUFF. Generic advice = rejected. Reference the niche, specific tools, real numbers.

Project niche: {niche}
Account name: {name}
Handle: @{handle}
Target platforms: {platforms}
Account angle: {angle}
Daily budget: ${budget}

=== FOUNDER NOTES / PAST FEEDBACK (OBEY THESE EXPLICITLY) ===
{mem}

=== CURRENT VIRAL TREND PATTERNS (match this energy) ===
{trends}

=== COMPETITIVE CONTEXT (top patterns in this niche right now) ===
{competitors}

Return STRICT JSON with 13 keys. Every value is a COMPLETE Markdown document (use headings,
bullets, tables, bold). Write like a real operator building a real business, not a student:

{{
  "executive_summary":  "markdown with: executive summary (3 sentences), business vision, 12-month goal, success metric, competitive moat, why this works now",
  "vision_mission":     "markdown with: vision statement, mission statement, 30/60/90-day goals, 12-month goals, brand values (3), archetype",
  "revenue_model":      "markdown with: revenue mix table (affiliate, ads, digital, sponsorships, UGC — % each), pricing tiers if digital, KPI targets (followers, RPM, CPM), expected $/month at 1k/10k/100k followers, break-even point",
  "brand_identity":     "markdown with: one-line promise, positioning statement, target audience (age/gender/location/pain/desire), 2 customer personas (name, age, job, pain, platform), voice (3 adjectives), do/don't list (5 each), example hooks (5), example CTAs (5), catchphrase",
  "visual_identity":    "markdown with: color palette (hex codes, primary/accent/pop/neutrals), typography (bold sans / display / body), image style (be SPECIFIC: phone closeups / flatlays / bokeh / isometric etc), video style (camera motion, transitions, pacing bpm), thumbnail formula, emoji signature, watermark position",
  "marketing_strategy": "markdown with: positioning statement, competitive analysis (3 competitor archetypes to study + what we do differently), SWOT (table), marketing funnel (top/mid/bottom), organic growth plan, paid strategy (when to turn ads on), community strategy (reply to X% of comments within Y hours), virality playbook (share triggers), collaboration strategy (who to collab with), influencer outreach list (types), cross-platform strategy (clip/repost flow), retention strategy (why they come back)",
  "instagram_playbook": "markdown with: feed strategy (theme/grid), reels strategy (length, hook frames, cover), stories strategy (polls/Qs/day), carousel strategy (structure, slide count), posting frequency, best posting times (specific hours), caption style (length/emojis/CTA), CTA rules, hashtag strategy (tiers), engagement SOP, growth tactics (5 specific)",
  "tiktok_playbook":    "markdown with: video strategy, hook formulas (6 that work NOW), retention strategy (pattern interrupt every 2-3 seconds), trend-jacking framework (how to adapt trends fast), posting schedule (times per day/week), hashtag strategy (broad/niche/brand), CTA framework, video length targets by stage, editing style (cuts, transitions, captions style), sound strategy (trending vs original, duck level)",
  "youtube_playbook":   "markdown with: shorts strategy (hook, title formula, thumbnail), long-form strategy (when to start, length, titles), title formulas (10 proven templates), thumbnail rules (contrast, face, text length), description template (hook/timestamps/links/CTA), SEO (tags, chapters, end screens), upload schedule, retention targets (30/60/90-day), monetization path (YPP requirements)",
  "content_calendar":   "markdown with: 1-week schedule table (Mon-Sun, platform, pillar, hook theme), 30-day outline (themes per week), seasonal calendar (key holidays/events in this niche over next 90 days), launch campaign (first 10 days), evergreen content list (10 topics), trending content trigger list (5 events to jump on), repurposing map (1 long → N shorts → M carousels → K tweets)",
  "content_rules":      "markdown with: 4 content pillars (with example topics each), hook patterns (8 specific examples), video structure (beat-by-beat standard), caption rules, FORBIDDEN list (no-repost rule, no banned claims), quality bar (what fails grading), CTA rotation (4 CTAs, rotate every 3 posts), hashtag policy, upload checklist",
  "hashtags_seo":       "markdown with: Tier-1 big tags (10, 1M+), Tier-2 mid tags (10, 100k-1M), Tier-3 niche tags (10, <100k), brand hashtag, SEO keywords (10 search terms people use), alt-text policy, YouTube tags template, TikTok SEO keywords",
  "production_sop":     "markdown with: step-by-step post production checklist, per-piece fields to fill (topic/objective/platform/angle/hook/script/caption/hashtags/keywords/CTA/thumbnail concept/image prompt/voiceover/edit notes), approval gate, publishing checklist (thumbnail, captions burned, hashtag set, first-comment pin), publishing window, archive naming convention"
}}"""


def run(limit: int = 1) -> int:
    accounts = _pending(limit)
    processed = 0
    for acc in accounts:
        if acc.get("paused"): continue
        if _project_is_paused(acc["project_id"]): continue
        try:
            _set_status(acc["id"], "architecting")
            events.emit("architect", f"Writing full business plan for @{acc['handle']} ({acc['name']}) — 13 docs…",
                        "info", "architect_start")
            mem = memory.context_block(account_id=acc["id"], project_id=acc["project_id"])
            try:
                from . import scout
                trends = scout.recent_trends(5)
            except Exception:
                trends = "pattern-interrupt hooks + 6-beat structure + upbeat lofi"
            competitors = _competitor_note(acc.get("niche","ai_tools"))
            docs = _generate_docs(acc, mem, trends, competitors)
            _save_docs(acc["id"], docs)
            # ---- RESEARCH BRIEF (competitive deep-dive) ----
            try:
                from . import research as _r
                niche = acc.get("niche","ai_tools")
                handle = acc.get("handle","account")
                angle = ((acc.get("platforms_config") or {}).get("angle")
                         or (acc.get("config") or {}).get("angle")
                         or f"{niche} tips, daily")
                findings = _r.research_account(
                    account_id=acc["id"], niche=niche, handle=handle, angle=angle,
                    project_id=acc.get("project_id"))
                # Also persist a markdown brief as a 14th doc (best effort)
                if findings:
                    try:
                        from supabase import create_client as _cc
                        brief_md = _research_to_markdown(niche, handle, findings)
                        _cc(config.get("SUPABASE_URL"), config.supabase_service_key()).table("account_documents").upsert({
                            "account_id": acc["id"], "doc_type": "research_brief",
                            "content": brief_md, "agent": "research"
                        }, on_conflict="account_id,doc_type").execute()
                    except Exception:
                        pass
            except Exception as _re:
                print(f"[architect] research brief skipped: {_re}")
            _set_status(acc["id"], "strategizing")
            memory.add(account_id=acc["id"], role="architect",
                      content=f"Full business plan written: {len(docs)} documents (executive summary through production SOP).",
                      metadata={"handle": acc["handle"]})
            events.emit("architect", f"✅ Full business plan for @{acc['handle']} complete. Handing to strategist.",
                        "success", "architect_done")
            processed += 1
        except Exception as e:
            _set_status(acc["id"], "needs_setup")
            events.error("architect", f"Architect failed for @{acc.get('handle','?')}: {str(e)[:200]}")
            ledger.record("architect", ok=False, detail=str(e)[:300])
    return processed


def _pending(limit: int):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    res = (sb.table("project_accounts")
           .select("*")
           .in_("status", ["needs_setup","architecting"])
           .eq("paused", False)
           .limit(50).execute())
    out = []
    for r in res.data or []:
        if _project_is_paused(r["project_id"]): continue
        out.append(r)
        if len(out) >= limit: break
    return out


def _project_is_paused(pid) -> bool:
    if not pid: return False
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        pj = sb.table("projects").select("paused").eq("id", pid).single().execute().data
        return bool(pj and pj.get("paused"))
    except Exception:
        return False


def _get_project(pid):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    return sb.table("projects").select("paused,name").eq("id", pid).single().execute().data


def _set_status(acc_id, status):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    sb.table("project_accounts").update({"status": status}).eq("id", acc_id).execute()


def _generate_docs(acc, mem: str, trends: str, competitors: str) -> dict:
    niche = acc.get("niche","AI tools"); name = acc.get("name","Account"); handle = acc.get("handle","account")
    plats = acc.get("platforms") or ["instagram","tiktok"]
    platforms = ", ".join(plats) if isinstance(plats,list) else str(plats)
    angle = ((acc.get("platforms_config") or {}).get("angle")
             or (acc.get("config") or {}).get("angle")
             or f"{niche} tips, daily")
    budget = acc.get("daily_budget_usd") or 0.5
    prompt = ARCHITECT_PROMPT.format(niche=niche, name=name, handle=handle, platforms=platforms,
                                     angle=angle, budget=budget, mem=mem[:4000],
                                     trends=trends[:2000], competitors=competitors[:1500])
    docs = None
    if llm.ready() and ledger.budget_ok(0.10):
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=7000)
            ledger.record("architect", model=mlabel, cost_usd=cost, detail=f"@{handle}")
            # Extract JSON (may be wrapped in markdown fences)
            t = text.strip()
            if "```" in t:
                t = t.split("```")[1]
                if t.startswith("json") or t.startswith("JSON"): t = t[4:]
            docs = json.loads(t[t.find("{"): t.rfind("}")+1])
        except Exception as e:
            ledger.record("architect", ok=False, detail=f"parse: {str(e)[:200]}")
    if not docs:
        docs = _fallback_docs(acc)
    # Validate + alias
    for dt in DOC_TYPES:
        if dt not in docs or not isinstance(docs[dt], str) or len(docs[dt]) < 80:
            docs[dt] = _fallback_doc(dt, acc)
    # Also write aliases for old 5-doc system
    for alias, real in DOC_ALIASES.items():
        docs.setdefault(alias, docs.get(real, ""))
    return docs


def _save_docs(acc_id, docs: dict):
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
    # Write the 13 real docs + aliases
    all_keys = list(DOC_TYPES) + list(DOC_ALIASES.keys())
    for dt in all_keys:
        content = docs.get(dt)
        if not content: continue
        sb.table("account_documents").upsert({
            "account_id": acc_id, "doc_type": dt, "content": content, "agent": "architect",
        }, on_conflict="account_id,doc_type").execute()


def _competitor_note(niche: str) -> str:
    return (f"Top {niche.replace('_',' ')} faceless accounts currently winning: fast hook in <1s, "
            "phone/UI closeups (no generic stock), 6-beat structure, single-verb CTA, "
            "lowercase captions, 10-15 well-targeted hashtags. They clone angles — never repost.")


def _fallback_docs(acc) -> dict:
    niche = (acc.get("niche") or "ai_tools").replace("_"," ")
    name = acc.get("name") or "Account"; handle = acc.get("handle") or "account"
    platforms = ", ".join(acc.get("platforms") or ["Instagram","TikTok"])
    angle = ((acc.get("platforms_config") or {}).get("angle") or f"{niche} tips")
    p = _niche_palette(acc.get("niche","ai_tools"))
    return {
      "executive_summary": textwrap.dedent(f"""\
# 📘 Executive Summary — @{handle}

**Account:** {name}
**Niche:** {niche}
**Angle:** {angle}
**Platforms:** {platforms}

## Vision
Deliver one specific, actionable {niche} win per post in under 60 seconds.
Build a faceless media brand that generates $3-10k/mo in affiliate + ad + digital revenue within 12 months.

## Why This Works Now
Demand for short-form {niche} content is growing faster than supply.
Faceless accounts scale without personal brand risk. Clone angles of winners, never repost.

## 12-Month Goal
- 50,000 followers across platforms
- 2,000 email subscribers
- $5,000/mo revenue
- 3 viral posts (1M+ views)
"""),
      "vision_mission": textwrap.dedent(f"""\
# 🎯 Vision & Mission — @{handle}

## Vision
Become the go-to daily resource for {niche} on short-form video.

## Mission
One concrete win per post. No fluff, no 10-minute essays. Just the answer.

## Goals
- **30 days:** Brand kit done, 30 posts planned, 5 drafts at ≥8/10 grade, 500 followers
- **60 days:** Posting daily, 2k followers, first affiliate link clicks
- **90 days:** 5k followers, first $100 revenue, 1 viral post (500k+ views)
- **12 months:** 50k followers, $5k/mo

## Brand Values
1. Specificity — show the exact button/prompt/link
2. Honesty — say when something sucks, don't shill
3. Speed — value in <8 seconds
"""),
      "revenue_model": textwrap.dedent("""\
# 💰 Revenue Model

| Stream | % of revenue |
|---|---|
| Affiliate marketing (tools we recommend) | 40% |
| Creator fund ad revenue | 30% |
| Digital products (checklists/toolkits) | 20% |
| Sponsorships (after 10k followers) | 10% |

## KPI Targets
| Milestone | Followers | Revenue/mo |
|---|---|---|
| Break-even | 1,000 | $50 |
| Side-income | 10,000 | $1,000 |
| Full-time | 50,000 | $5,000 |
| Scale | 100,000+ | $15,000+ |

## RPM/CPM Benchmarks
- TikTok Shorts: $0.30-$0.50 RPM
- YouTube Shorts: $0.40-$0.80 RPM
- IG Reels bonus: varies
- Affiliate EPC: $0.20-$2.00 per click
"""),
      "brand_identity": textwrap.dedent(f"""\
# 🎨 Brand Identity — @{handle}

## One-line Promise
One {niche} win per day in under 60 seconds.

## Archetype
The Sharp Friend — smarter than average, never condescending.

## Target Audience
- 18-34, English-speaking
- Overwhelmed by noise, wants one specific answer
- Pain point: 100 tutorials, none specific enough

## Personas
- **Alex, 24** — junior professional, side-hustle curious, scrolls TikTok on commute
- **Sam, 30** — content creator looking for tools to speed up workflow, on IG + YouTube

## Voice
Direct · Playful · Specific

## Do
1. Open with a pattern-interrupt hook (<=8 words)
2. "You" > "I" (3x more)
3. Sentences <=12 words
4. End every post with a single-verb CTA
5. Lowercase captions

## Don't
- "Hey guys" / "let's talk about" / "in this video"
- "Game changer" / "revolutionary" / "you won't believe"
- Fake urgency / fake screenshots
- Repost other creators (banned)
- "Get rich quick" / overclaim

## Catchphrase
"That's it — one move a day."
"""),
      "visual_identity": textwrap.dedent(f"""\
# 🎬 Visual Identity — @{handle}

## Palette
{p}

## Typography
- Bold titles: DejaVu Sans Bold (heavy weight, 110pt on reel)
- Body: clean sans-serif
- Power word highlight: yellow (#fde047) with 9px black outline

## Image Style
Primary: phone screen closeups, UI zoom-ins, isometric 3D icons, over-shoulder laptop.
No generic stock photos, no AI people faces, no wallpaper gradients without subjects.

## Video Style
- 9:16 vertical, 1080x1920
- Slow push-in (Ken Burns) on every frame
- Zoom-punch cuts between beats
- Pattern-interrupt hook poster for first 1.2s
- Dark bottom-third for subtitles
- Progress dots across top

## Thumbnail Formula
- 1-3 bold words in top third (brand accent color)
- Circular reaction sticker top-right
- Darkened bottom third for subtitle safety
- High contrast, reads at 120px tall
"""),
      "marketing_strategy": textwrap.dedent("""\
# 📣 Marketing Strategy

## Positioning
The no-fluff daily win for the niche. Not a guru, not a course-seller — the friend who actually uses the tools.

## SWOT
| | Helpful | Harmful |
|---|---|---|
| Internal | Specific, fast, replicable system | Faceless (no personal brand) |
| External | Algorithm loves short hooks | High competition, repost bans |

## Marketing Funnel
- **Top of funnel** (discover): hooks that interrupt scroll, trending sounds, broad hashtags
- **Middle** (engage): carousels/deep-dives for save rate, comment bait questions
- **Bottom** (convert): soft CTA to follow/save, then link-in-bio for affiliate/digital

## Organic Growth
- Post 1x/day on main platform, cross-post within 6h to others
- Reply to 20 comments per post within first hour
- Jump on trends within 24h
- Pin a comment with a question

## Virality Playbook
Share triggers: surprising stat, contrarian take, "this changed everything" reveal,
specific number, easily-savable checklist. Engineer for rewatchability (CTA at end
pushes replay).

## Cross-platform Flow
- Native 1st on TikTok → IG Reels (within 2h) → YT Shorts (same day)
- Carousels on IG only
- 1 thread/week on X
"""),
      "instagram_playbook": textwrap.dedent("""\
# 📸 Instagram Playbook

## Feed Strategy
Clean grid, alternating colors, 3-post pattern (reel, carousel, quote) for visual rhythm.

## Reels Strategy
30-40s, hook in first 1s, 6 beats, burned-in kinetic captions. Cover: bold 2 words on dark.

## Stories Strategy
3-5 stories/day: behind-the-scenes, polls ("which tool next?"), countdown, Q sticker.

## Carousels
8-10 slides: hook → 5 tips → CTA save/follow. Pin top comment.

## Posting
- 1 Reel / day
- Best times: 7am, 12pm, 7pm local
- Caption: lowercase, 2-3 lines, 1 emoji/line, CTA last

## Hashtags
3 big + 4 medium + 3 niche (see hashtags_seo doc).

## Engagement SOP
- Reply to 20 comments/hour for first 2h
- Like 10 niche comments per day
"""),
      "tiktok_playbook": textwrap.dedent("""\
# 🎵 TikTok Playbook

## Hook Formulas
1. Two-word stop: "stop scrolling."
2. Number list: "3 tools that replaced my job."
3. Contrarian: "most [niche] advice is wrong."
4. Secret: "nobody talks about this."
5. Demo: "just press this button."
6. Warning: "you're doing it wrong."

## Retention
Pattern interrupt every 2-3 seconds (cut, zoom-punch, whip, flash). No static shots >3s.
Voice must keep moving. Reveal payoff only at end.

## Trends
Jump on sounds within 24h. Clone the ANGLE (don't repost). Adapt every trend to niche.

## Schedule
- 1 video/day at 8am, 2pm, or 8pm
- 10-15 hashtags: 5 big, 6 medium, 4 niche
- CTA: single verb ("follow", "save", "comment LINK")
- Length: 28-38s for reels, 22-28s for hooks-heavy

## Editing
Fast cuts, punch zooms, flash transitions, SFX on every cut, -12dB duck music under voice.
"""),
      "youtube_playbook": textwrap.dedent("""\
# ▶️ YouTube Playbook

## Shorts
Same videos as TikTok but remove platform-specific watermarks. Title = hook as question or bold claim.
Custom thumbnail with 2-word text + color. Upload within 24h of TikTok.

## Long-form (Month 4+)
Start when 3 shorts hit >100k views. 8-12 min tutorials. Chapters pinned in description.

## Title Templates
- "I Tried [X] for 30 Days (shocking results)"
- "[X] — Explained in 60 Seconds"
- "Stop Using [X] — Use This Instead"
- "3 [X] That Actually Work in 2025"
- "How I [Result] Using Only [Tool]"

## Thumbnails
High contrast, 2-4 words max, bright accent color, emotional reaction, read at tiny size.

## Upload Schedule
Shorts: daily at 9am. Long-form: every other Saturday.
SEO tags: mix of broad + niche keywords in title + first 2 lines of description.
"""),
      "content_calendar": textwrap.dedent(f"""\
# 📅 Content Calendar

## Weekly Rhythm
| Day | Platform | Pillar | Hook Theme |
|---|---|---|---|
| Mon | TikTok/IG/YT | Quick tip | Tool/shortcut |
| Tue | TikTok/IG | Deep dive | How-to |
| Wed | TikTok/IG + carousel | Mistake | "You're doing X wrong" |
| Thu | TikTok/IG/YT | Quick tip | Number list |
| Fri | TikTok/IG | Results / proof | "Here's what happened" |
| Sat | TikTok/IG | Reaction / trend | Adapt sound |
| Sun | TikTok/IG | Roundup | "Week's best" |

## 30-Day Outline
Week 1: Foundation hooks + quick wins (train algorithm)
Week 2: Mistakes to avoid (high save-rate)
Week 3: Proof / results posts (trust build)
Week 4: Roundups / lists (shareable)

## Repurposing Map
- 1 script → 1 reel (primary)
- Same hook/topic → 3-frame IG story teaser
- Script text → 8-slide carousel 2 days later
- 3 best points → X thread
- 5 scripts → 1 long-form video (after month 3)
"""),
      "content_rules": textwrap.dedent("""\
# 📐 Content Rules

## Pillars
1. ⚡ Quick tip (<30s, one tool/shortcut)
2. 🔍 Deep dive (60s how-to)
3. ❌ Don't do this (mistake + fix)
4. 📊 Results / proof (screenshots, earnings, metrics)

## Hook Patterns
- Pattern interrupt (2 words)
- Bold contrarian claim
- Specific number
- Direct question
- Secret reveal
- Demo show-don't-tell
- Warning/mistake
- Result-first ($/follower count)

## Video Structure
1. Hook poster (1.2s)
2-6. 4-5 body beats (one idea each, 3-4s)
7. CTA end card (2.5s)

## Forbidden
- No "hey guys" / "in today's video" / "let's talk about"
- No "game changer" / "revolutionary"
- No fake screenshots / fake claims
- No straight reposting (ban risk)
- No crypto/NFT/get-rich-quick shilling
- No overclaiming

## CTA Rotation (every 3 posts)
1. "follow for one move a day."
2. "save this before it's gone."
3. "comment 'LINK' and i'll send it."
4. "share with a friend who needs this."
"""),
      "hashtags_seo": textwrap.dedent(f"""\
# 🔖 Hashtags & SEO — @{handle}

## Broad Tier (3M+ posts)
#{niche.replace(' ','')} #tips #viral #fyp #learn

## Medium Tier (100k-3M)
#{niche.replace(' ','')}tips #{niche.replace(' ','')}hack #learn{niche.replace(' ','')} #sidehustle

## Niche Tier (<100k)
#daily{niche.replace(' ','')} #{handle} #{niche.replace(' ','')}101

## Brand Hashtag
#{handle}

## SEO Keywords (include in caption + YT description)
{niche} tips, best {niche} tools, how to {niche}, {niche} tutorial, {niche} for beginners, {niche} shortcut
"""),
      "production_sop": textwrap.dedent("""\
# ✅ Production SOP (every post)

## Fields Filled Before Production
- [ ] Topic
- [ ] Objective (awareness / save / click / follow)
- [ ] Platform
- [ ] Angle (which trend pattern are we cloning)
- [ ] Hook (<=8 words)
- [ ] Script (6-7 beats, voiceover per beat)
- [ ] Caption (lowercase, 2-3 lines, 1 emoji/line, CTA)
- [ ] Hashtags (3+4+3 set)
- [ ] Keywords (for SEO)
- [ ] CTA (single verb)
- [ ] Thumbnail concept (2-word hook)
- [ ] Visual prompt per beat (specific shot, no generic)
- [ ] Voiceover script
- [ ] Editing notes (transitions, SFX)

## Pre-Publish Checklist
- [ ] Grader scored >= 8/10
- [ ] Hook audible in first 1 second
- [ ] Captions burned in, kinetic
- [ ] No typoes
- [ ] Audio levels balanced (voice loudest, music ducked)
- [ ] Thumbnail/cover chosen
- [ ] Hashtag set loaded
- [ ] First-comment pinned (question to drive engagement)
- [ ] Link-in-bio updated if needed
- [ ] Posted during window (7am/12pm/7pm local)
"""),
    }


def _niche_palette(slug: str) -> str:
    m = {
      "ai_tools":"Primary: #0f172a (navy) · Accent: #22d3ee (cyan) · Pop: #ef4444 · Neutrals: #fafaf9, #1e293b",
      "fitness":"Primary: #0c0a09 · Accent: #f97316 (orange) · Pop: #dc2626 · Neutrals: #f5f5f4, #292524",
      "cooking":"Primary: #422006 · Accent: #f59e0b (amber) · Pop: #ef4444 · Neutrals: #fef3c7, #1c1917",
      "skincare":"Primary: #fce7f3 · Accent: #ec4899 (pink) · Pop: #8b5cf6 · Neutrals: #fdf2f8, #500724",
      "cats":"Primary: #1e1b4b · Accent: #fbbf24 (gold) · Pop: #a855f7 · Neutrals: #fef3c7, #0c0a09",
      "pets":"Primary: #064e3b · Accent: #fbbf24 (gold) · Pop: #f97316 · Neutrals: #ecfccb, #052e16",
    }
    return m.get(slug, "Primary: #0f172a · Accent: #22d3ee (cyan) · Pop: #ef4444 · Neutrals: #fafaf9, #1e293b")


def _fallback_doc(dt: str, acc) -> str:
    return _fallback_docs(acc).get(dt, f"# {dt}\n\nTo be written.")


def _research_to_markdown(niche: str, handle: str, findings: dict) -> str:
    import textwrap as _tw
    qs = findings.get("top_questions", [])
    angles = findings.get("competitor_angles", [])
    kws = findings.get("keywords", [])
    return _tw.dedent(f"""\
# 🔎 Research Brief — @{handle}

**Niche:** {niche}

## Top Audience Questions (answer these in posts)
""" + "\n".join(f"- {q}" for q in qs) + """

## Proven Competitor Angles (CLONE THE ANGLE — never repost)
""" + "\n".join(f"- {a}" for a in angles) + """

## SEO Keywords (include in captions/hashtags)
""" + ", ".join(kws) + """

## Rule
Never straight repost another creator's content. Clone the PATTERN (the angle, structure, hook type) and produce original content from it.
""")
