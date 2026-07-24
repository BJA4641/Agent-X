"""grader.py — Content Grader agent v4.1.
Scores every finished script across 6 dimensions (hook/visuals/pacing/audio/caption/cta),
1-10 each, with an overall average. Content below MIN_GRADE (8.0) is auto-rejected
with a concrete fix instruction — the brain rewrites it up to MAX_ATTEMPTS times.
"""
import os as _os_g
from . import config, ledger, llm, events
try:
    from . import memory
except Exception as _e:
    print(f"[grader] WARNING: memory import failed ({_e}); using no-op stub.")
    from . import _memstub
    memory = _memstub.MemoryStub()
import json

MIN_GRADE = 8.0
MAX_ATTEMPTS = 2

GRADER_PROMPT = """You are a ruthless TikTok/Reels/Shorts CREATIVE DIRECTOR grading one vertical short-form script.
Be BRUTALLY HONEST. Grading scale (do NOT inflate):
  1-4  = garbage / ad / corporate / boring — dies instantly
  5-6  = generic, scrollable, doesn't offend but won't travel
  7    = passable, gets a few hundred views, won't go viral
  8    = publishable — good hook, solid visuals, could get 10k+
  9-10 = HAS real viral potential — pattern interrupt, specific, cinematic, makes you rewatch

Account memory / founder guidance (OBEY these notes):
{memory}

Previous grade feedback on this account — NEVER repeat these mistakes:
{past_feedback}

Current viral trend patterns to match the energy of (clone the ANGLE, not the words):
{trends}

Content to grade (script + shot plan):
{content}

ANCHORS (v5.11.8 — keep grading consistent across runs; the writer prompt now
carries this same rubric, so a low score means the script genuinely missed it):
  hook 4 = "Learn about skincare" · hook 7 = "Three actives, eight weeks"
         · hook 9 = "Most smart feeders starve puppies."
  visuals 4 = "AI innovation" (abstract) · visuals 9 = "a cracked phone screen
         on a kitchen counter, hard morning light"
  cta 5 = "check the link in bio and also follow" · cta 9 = "save this."

`human` (v5.11.12) — does this sound like a PERSON talking, or like a model?
  1-4  = AI tells: "in today's video we'll explore", "let's dive in", "game-changer",
         "revolutionise", tidy tricolons, every sentence the same length, no contractions
  5-6  = competent but flat; correct sentences nobody would say out loud
  7    = mostly natural, one or two stock phrases
  8-10 = sounds like a real person with an opinion — contractions, uneven rhythm,
         one specific concrete detail a model would not invent
This axis exists because the other six can all pass while the script still reads
as machine-written, which is the fastest way to lose a short-form audience.

Score 1-10 on EACH axis. Return STRICT JSON with no commentary:
{{
  "hook": int,
  "visuals": int,
  "pacing": int,
  "audio": int,
  "caption": int,
  "cta": int,
  "human": int,
  "notes": "two sentences: what WORKS specifically",
  "fix_instruction": "ONE concrete rewrite instruction — what to change, exactly. If overall >= 8, say exactly 'publish'"
}}"""

REWRITE_PROMPT = """You are the same CREATIVE DIRECTOR. The previous draft scored {overall}/10 and failed.
FIX INSTRUCTION FROM GRADER (address every word of this):
{fix}

Previous rejected draft (for reference — DO NOT reuse the same hook/words):
{previous}

Memory / founder guidance to obey:
{memory}

Current viral trend patterns to match:
{trends}

Account brand — tone, visuals, content rules:
{brand}

Topic: {topic}

REWRITE the script completely. Return the SAME strict JSON shape as a fresh script_v3 output
(hooks, title, hashtags, caption, beats[6-7]) with the fix applied. Keep hooks <=8 words,
6-7 beats total (hook + body + CTA), on_screen_text MAX 3 words."""


def grade_post(script: dict, account_id=None, project_id=None, post_id=None, item_id=None,
               brand_context: dict = None, force_claude: bool = False) -> dict:
    """Returns {'passed':bool, 'scores':{...}, 'overall':float, 'notes':str, 'fix':str, 'attempts_made':int}"""
    content = json.dumps({
        "hook": script.get("hook"),
        "title": script.get("title"),
        "caption": script.get("caption"),
        "hashtags": script.get("hashtags"),
        "beats": [{
            "voiceover": b.get("voiceover") or b.get("text"),
            "on_screen_text": b.get("on_screen_text"),
            "visual_prompt": b.get("visual_prompt") or b.get("image_prompt"),
            "visual_source": b.get("visual_source"),
            "camera": b.get("camera"),
            "sfx": b.get("sfx"),
            "duration_ms": b.get("duration_ms"),
        } for b in (script.get("beats") or [])],
    }, indent=2)[:6000]

    mem = memory.context_block(account_id, project_id)
    past = memory.load_grade_feedback(account_id, project_id)
    try:
        from . import scout
        trends = scout.recent_trends(4)
    except Exception:
        trends = "pattern_interrupt hooks + 6 beats + upbeat lofi bed"

    prompt = GRADER_PROMPT.format(
        memory=mem, past_feedback=past or "none", trends=trends, content=content)
    # v5.8.2: the judge reads its expert rubric playbook (skills/cqo/SKILL.md)
    try:
        from agentcore import skills as _sk
        prompt += _sk.skill_block("cqo")
    except Exception:
        pass

    verdict = _default_verdict()
    # v5.8.7: free-council grading costs $0 -> not gated on the paid budget.
    from agentcore import costmode as _cm
    _free_available = any(_cm.has_key(p) for p in ("gemini", "groq", "openrouter"))
    _gate = _free_available or (llm.ready() and _cm.may_spend(0.015))
    if not _gate:
        # v5.7.1: grader can't actually run (no LLM key or daily budget spent).
        # Say so honestly instead of emitting fake 6.0 scores that trigger
        # PAID rewrites. Caller must park the draft, not rewrite it.
        verdict["skipped"] = True
        verdict["notes"] = "grader skipped — LLM unavailable or daily budget exhausted"
        verdict["fix"] = "hold for human review"
    if _gate:
        try:
            # v5.8.6 FREE-FIRST GRADING (founder mandate: Anthropic = final audit only).
            #   normal attempts  → free council model grades ($0)
            #   force_claude     → one paid Claude call, used ONLY by the CQO
            #                      final-audit step on the winning script.
            text = cost = mlabel = None
            if force_claude:
                from agentcore import aisuite as _ais
                # v5.10.8 REQ-CHEAP-TEXT: grading is classification against a rubric,
                # not open-ended reasoning. Hard-pinning sonnet cost $0.16 across 12
                # calls for work a cheap model does at ~1/10th. Overridable by env
                # when a genuine quality audit is wanted.
                text, _meta = _ais.generate_text(prompt, model=_os_g.environ.get("GRADER_MODEL") or None,
                                                 tier=_os_g.environ.get("GRADER_TIER", "cheap"),
                                                 max_tokens=500)
                cost, mlabel = float(_meta.get("cost_usd") or 0), _meta.get("model", "claude-sonnet-4-5")
                ledger.record("grader.final_audit", model=mlabel, cost_usd=cost, item_id=item_id)
            else:
                try:
                    from agentcore import council as _council
                    text, cost, mlabel = _council.free_chat(prompt, max_tokens=500)
                except Exception:
                    if config.get("ALLOW_PAID_GRADER") == "1":
                        text, cost, mlabel = llm.chat(prompt, max_tokens=500)
                    else:
                        raise  # no free grader + paid not allowed → skipped verdict below
                ledger.record("grader", model=mlabel, cost_usd=cost, item_id=item_id)
            parsed = json.loads(text[text.find("{"): text.rfind("}")+1])
            scores = {k: _clamp(int(parsed.get(k, 5)), 1, 10)
                      for k in ("hook","visuals","pacing","audio","caption","cta")}
            overall = round(sum(scores.values()) / 6.0, 1)
            verdict = {
                "scores": scores,
                "overall": overall,
                "passed": overall >= MIN_GRADE,
                "notes": str(parsed.get("notes","")),
                "fix": str(parsed.get("fix_instruction","publish")),
            }
        except Exception as e:
            ledger.record("grader", ok=False, detail=str(e)[:300], item_id=item_id)
            # v5.8.6: "no free provider available" is NOT a content failure —
            # park the draft honestly instead of emitting fail-safe scores
            # that would trigger rewrites of a possibly fine script.
            if "no free provider" in str(e).lower():
                verdict = _default_verdict(str(e))
                verdict["skipped"] = True
                verdict["notes"] = "grader skipped — free models unavailable (rate limits?)"
                verdict["fix"] = "hold for human review"
            else:
                verdict = _default_verdict(str(e))

    # Save to DB + memory
    _save_grade(verdict, post_id, item_id)
    events.emit("grader",
                f"Grade: {verdict['overall']}/10 — hook {verdict['scores']['hook']}, visuals {verdict['scores']['visuals']}, pacing {verdict['scores']['pacing']}, audio {verdict['scores']['audio']}, caption {verdict['scores']['caption']}, cta {verdict['scores']['cta']} — "
                + ("PASS ✅" if verdict["passed"] else f"NEEDS FIX: {verdict['fix'][:90]}"),
                "success" if verdict["passed"] else "warn",
                "grade_pass" if verdict["passed"] else "grade_fail",
                item_id=item_id)

    sc = verdict["scores"]
    mem_note = (f"grade={verdict['overall']}/10 (h{sc['hook']} v{sc['visuals']} p{sc['pacing']} "
                f"a{sc['audio']} c{sc['caption']} C{sc['cta']}) — "
                + ("PUBLISH" if verdict["passed"] else f"REJECT: {verdict['fix']}"))
    if account_id:
        memory.add(account_id=account_id, role="grader", content=mem_note,
                  metadata={"passed": verdict["passed"], "scores": verdict["scores"],
                            "overall": verdict["overall"]})
    return verdict


def rewrite_script(previous_script: dict, verdict: dict, topic: str,
                   account_id=None, project_id=None, brand_context: dict = None) -> dict:
    """Ask the LLM for a full rewrite based on grader feedback."""
    from . import scout
    mem = memory.context_block(account_id, project_id)
    trends = scout.recent_trends(4)
    brand = ""
    if brand_context:
        brand = "\n".join(f"=== {k.upper()} ===\n{v}" for k, v in brand_context.items() if v)
    prompt = REWRITE_PROMPT.format(
        overall=verdict["overall"], fix=verdict["fix"],
        previous=json.dumps(previous_script)[:3000],
        memory=mem, trends=trends, brand=brand or "(none yet)", topic=topic)
    from agentcore import costmode as _cm2
    if not (any(_cm2.has_key(p) for p in ("gemini", "groq", "openrouter"))
            or (llm.ready() and _cm2.may_spend(0.025))):
        return previous_script
    try:
        # v5.8.6: rewrites are free-council work too; paid only if explicitly allowed.
        try:
            from agentcore import council as _council
            text, cost, mlabel = _council.free_chat(prompt, max_tokens=1800)
        except Exception:
            if config.get("ALLOW_PAID_WRITER") == "1":
                text, cost, mlabel = llm.chat(prompt, max_tokens=1800)
            else:
                raise
        ledger.record("brain_rewrite", model=mlabel, cost_usd=cost)
        parsed = json.loads(text[text.find("{"): text.rfind("}")+1])
        return parsed
    except Exception as e:
        ledger.record("brain_rewrite", ok=False, detail=str(e)[:200])
        return previous_script


def _clamp(n, lo, hi):
    return max(lo, min(hi, n))


def _default_verdict(note: str = "") -> dict:
    return {
        "scores": {"hook":6,"visuals":6,"pacing":6,"audio":6,"caption":6,"cta":6,"human":6},
        "overall": 6.0,
        "passed": False,
        "notes": note or "Grader unavailable — defaulting to fail-safe.",
        "fix": "Rewrite with a harder-hitting pattern-interrupt hook (<=5 words), specific UI/phone closeup visuals, 6 tight beats, single-verb CTA, and casual lowercase caption.",
    }


def _save_grade(v: dict, post_id=None, item_id=None):
    if not config.HAS_SUPABASE: return
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        sb.table("content_grades").insert({
            "tenant_id": config.TENANT_ID,
            "post_id": post_id, "item_id": item_id,
            "hook": v["scores"]["hook"], "visuals": v["scores"]["visuals"],
            "pacing": v["scores"]["pacing"], "audio": v["scores"]["audio"],
            "caption": v["scores"]["caption"], "cta": v["scores"]["cta"],
            "overall": v["overall"], "passed": v["passed"],
            "notes": v["notes"], "fix_instruction": v["fix"],
        }).execute()
    except Exception as e:
        print(f"[grader] save failed: {e}")
