"""brand.py — the Brand Bible agent.

First-run for every new tenant: asks 10 onboarding questions, builds a structured
Brand Bible, persists it to the `brand_profiles` table, and makes it available
to every other module. All downstream prompts (brain.caption, brain.write_script,
distribution.repurpose, community.draft_replies, visuals.pick_style) should read
this via brand.profile_for(user_id) and inject a `{brand_grounding}` block at the
top of their prompt.

This is the single highest-ROI change for SaaS quality. Without a Brand Bible,
every client gets the same voice; with it, 100 clients sound like 100 brands.
"""
from __future__ import annotations
import json, os
from . import config, ledger, llm

EST_COST = 0.02

QUESTIONNAIRE = [
    "What is your brand name and one-sentence description of what you sell/do?",
    "What vertical are you in? (e.g. SaaS, DTC skincare, fitness coaching, real estate)",
    "Describe your target audience in one paragraph: age, what they struggle with, what they secretly want.",
    "Pick 3 words your brand SOUNDS like (e.g. warm, snarky, authoritative, playful, calm, bold).",
    "Pick 3 words your brand MUST NEVER sound like.",
    "Are emojis allowed? (none / light / heavy) What about profanity or slang?",
    "Who are 3 competitors or similar accounts you want to sound LIKE and/or UNLIKE?",
    "What are your 3-5 content pillars (recurring themes) if you have them? (we'll fill gaps with research otherwise)",
    "Brand hex colors and any visual assets? (primary/secondary/accent hex codes, or 'I don't know yet')",
    "What topics or angles are completely OFF LIMITS (politics, religion, health claims, competitor shade)?",
]


def profile_for(user_id: str = None) -> dict:
    """Return the Brand Bible dict for a user, or the default factory brand."""
    uid = user_id or config.TENANT_ID
    if config.HAS_SUPABASE and uid != "me":
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
            r = sb.table("brand_profiles").select("*").eq("user_id", uid).limit(1).execute().data
            if r:
                return _format_for_prompt(r[0])
        except Exception:
            pass
    # Local single-tenant default
    return _format_for_prompt(_local_default())


def _local_default() -> dict:
    return {
        "brand_name": config.get("BRAND_NAME", ""),
        "vertical": config.get("BRAND_VERTICAL", "tech creators"),
        "voice_tone": {
            "formality": config.get("VOICE_FORMALITY", "conversational"),
            "humor": config.get("VOICE_HUMOR", "dry"),
            "person": config.get("VOICE_PERSON", "2nd"),
            "emoji_policy": config.get("VOICE_EMOJIS", "light"),
            "forbidden_words": json.loads(config.get("FORBIDDEN_WORDS", "[]") or "[]"),
            "example_lines": json.loads(config.get("VOICE_EXAMPLES", "[]") or "[]"),
        },
        "audience": json.loads(config.get("AUDIENCE", "[]") or "[]"),
        "pillars": json.loads(config.get("PILLARS", "[\"tutorials\", \"news\", \"tools\"]")),
        "visual_id": {
            "palette": {
                "primary": config.get("COLOR_PRIMARY", "#0b0c10"),
                "secondary": config.get("COLOR_SECONDARY", "#1f2833"),
                "accent": config.get("COLOR_ACCENT", "#66fcf1"),
            }
        },
        "cta_line": config.get("CTA_LINE", "Follow for more."),
        "do_list": json.loads(config.get("DO_LIST", "[]") or "[]"),
        "dont_list": json.loads(config.get("DONT_LIST", "[]") or "[]"),
        "risk_register": json.loads(config.get("RISK_REGISTER", "[]") or "[]"),
    }


def _format_for_prompt(row: dict) -> str:
    """Turn a brand_profiles row into a markdown block that can be dropped into any prompt."""
    voice = row.get("voice_tone") or {}
    vis = row.get("visual_id") or {}
    palette = (vis.get("palette") or {})
    return f"""
# BRAND GROUNDING — {row.get('brand_name','')} ({row.get('vertical','')})

VOICE:
- Formality: {voice.get('formality','conversational')}
- Humor: {voice.get('humor','none')}
- POV: {voice.get('person','2nd')} person
- Emojis: {voice.get('emoji_policy','light')}
- Forbidden words: {voice.get('forbidden_words') or 'none'}
- Sound-like examples: {voice.get('example_lines') or 'none'}

AUDIENCE:
{json.dumps(row.get('audience') or [], indent=2)}

CONTENT PILLARS: {row.get('pillars') or []}

VISUAL ID:
- Primary/secondary/accent hex: {palette.get('primary','#000')} / {palette.get('secondary','#444')} / {palette.get('accent','#08f')}
- Imagery style: {vis.get('imagery_style','clean editorial')}

CTA LINE: {row.get('cta_line','Follow for more.')}

DO: {json.dumps(row.get('do_list') or [])}
DON'T: {json.dumps(row.get('dont_list') or [])}
OFF-LIMITS (never touch these): {json.dumps(row.get('risk_register') or [])}

IMPORTANT: Every sentence you write must match this voice. Reject any angle,
joke, or word that conflicts with DON'T or OFF-LIMITS.
"""


def generate_from_answers(answers: dict, user_id: str = None) -> dict:
    """
    Build a structured Brand Bible from onboarding answers.
    `answers` is a dict of {question_idx: answer_text}.
    Calls the LLM to fill in missing pillars/voice/audience depth, then persists.
    Returns the profile row written to the DB.
    """
    uid = user_id or config.TENANT_ID
    qa_text = "\n".join(f"Q{i+1}: {QUESTIONNAIRE[i]}\nA{i+1}: {answers.get(i, '')}" for i in range(len(QUESTIONNAIRE)))
    if llm.ready() and ledger.budget_ok(EST_COST):
        prompt = f"""You are a senior brand strategist for a social-first content agency.
Given the following client onboarding answers, produce a structured Brand Bible
as a single JSON object with these keys:
- brand_name (string)
- vertical (string)
- voice_tone: object with keys formality, humor, person ("1st","2nd","3rd"),
  emoji_policy ("none","light","heavy"), forbidden_words (array of strings),
  sentence_length ("short","mixed","long"), example_lines (array of 3 sample
  captions written IN this brand's voice, max 15 words each)
- audience: array of 1-3 persona objects, each with name, age_range, pain_points
  (array), desires (array), media_diet (array)
- pillars: array of 3-5 content pillar strings
- visual_id: object with palette {{primary, secondary, accent}} (hex codes),
  imagery_style, fonts {{heading, body}}, safe_zones
- cta_line (string)
- do_list (array of 5 specific do's)
- dont_list (array of 5 specific don'ts)
- risk_register (array of off-limits topics/angles)

CLIENT ANSWERS:
{qa_text}

Output ONLY the JSON object, nothing else."""
        text, cost, mlabel = llm.chat(prompt, max_tokens=1200)
        try:
            profile = json.loads(text[text.find("{"): text.rfind("}") + 1])
            ledger.record("brand", model=mlabel, prompt_version="brand_v1", cost_usd=cost)
        except Exception as e:
            ledger.record("brand", ok=False, detail=f"json parse: {e}")
            profile = _answers_to_profile_simple(answers)
    else:
        profile = _answers_to_profile_simple(answers)

    profile["onboarding_done"] = True
    if config.HAS_SUPABASE and uid != "me":
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
            sb.table("brand_profiles").upsert({"user_id": uid, **profile}).execute()
        except Exception as e:
            ledger.record("brand", ok=False, detail=f"db upsert: {e}")
    return profile


def _answers_to_profile_simple(answers: dict) -> dict:
    """Fallback: build a minimal profile from raw answers without the LLM."""
    return {
        "brand_name": answers.get(0, "").split(".")[0][:60],
        "vertical": answers.get(1, "general"),
        "voice_tone": {"emoji_policy": "light", "forbidden_words": [], "person": "2nd",
                       "humor": "light", "formality": "conversational", "example_lines": []},
        "audience": [{"name": "primary", "pain_points": [answers.get(2, "")[:200]]}],
        "pillars": [s.strip() for s in (answers.get(7, "") or "").split(",") if s.strip()][:5] or ["value", "behind-the-scenes", "offers"],
        "visual_id": {"palette": {}},
        "cta_line": "Follow for more.",
        "do_list": ["speak conversationally", "provide value", "use clear CTA"],
        "dont_list": ["be generic", "use clickbait", "oversell"],
        "risk_register": [r.strip() for r in (answers.get(9, "") or "").split(",") if r.strip()],
    }


# ---- Injection helper for every other agent ---------------------------
# Use in brain/community/distribution prompts like:
#   prompt = BRAND_HEADER(user_id) + "\n\n" + prompt_template.format(...)
def grounding_block(user_id: str = None) -> str:
    """Return a ready-to-paste markdown grounding block."""
    return str(profile_for(user_id))
