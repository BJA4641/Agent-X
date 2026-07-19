"""brain.py — scriptwriting. Claude (live) or a bundled demo library (dry-run).
Prompt loaded from prompts/script_v1.md; version stamped into the ledger."""
import json, random
from . import config, ledger, board, llm

CTA_LINE = config.get("CTA_LINE", "Follow for one AI move a day.")
EST_COST = 0.01  # rough per-script cost guard

_DEMO = [
    {"hook": "Your browser has a free AI you never opened.",
     "hook_options": ["Your browser has a free AI you never opened.", "Chrome hid an AI on your laptop.", "Why is nobody using Chrome's built-in AI?"],
     "beats": [
        {"text": "Chrome now ships an on-device AI model.", "image_prompt": "glowing neural chip inside a laptop, cinematic macro, cool blue"},
        {"text": "It summarizes any page without sending data out.", "image_prompt": "clean desk, laptop with abstract summary cards floating, soft light"},
        {"text": "Writers use it to fix tone in one click.", "image_prompt": "hands on keyboard, warm lamp, text morphing on screen"},
        {"text": "And it works offline on a plane.", "image_prompt": "airplane window seat, laptop glow, night clouds"}],
     "cta": CTA_LINE},
    {"hook": "Stop paying for transcription. This is free.",
     "hook_options": ["Stop paying for transcription. This is free.", "This free tool subtitles anything in minutes.", "Still paying for captions? Read this."],
     "beats": [
        {"text": "Whisper runs on your own computer.", "image_prompt": "audio waveform turning into text, dark studio, neon accents"},
        {"text": "Drop in a file, get subtitles in minutes.", "image_prompt": "drag and drop file into glowing folder, minimal 3d"},
        {"text": "It handles 90 plus languages.", "image_prompt": "globe of flowing multilingual glyphs, elegant dark scene"},
        {"text": "Creators caption every video with it.", "image_prompt": "phone with captioned vertical video, studio ring light"}],
     "cta": CTA_LINE},
]

def write_script(topic: str, item_id=None, context: str = None) -> dict:
    if llm.ready() and ledger.budget_ok(EST_COST):
        prompt, version = config.load_prompt("script_v3")
        prompt = (prompt.replace("{topic}", topic).replace("{cta_line}", CTA_LINE)
                  .replace("{editor_notes}", editor_notes()).replace("{liked_hooks}", hook_taste()))
        if context:
            prompt += ("\n\nCONTEXT FROM THE SCOUT/PROJECT (use for specificity; NEVER invent stats):\n"
                       + str(context)[:600])
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=800)
            script = json.loads(text[text.find("{"): text.rfind("}") + 1])
            hooks = script.pop("hooks", None) or ([script.get("hook")] if script.get("hook") else [])
            script["hook"], script["hook_options"] = hooks[0], hooks[:3]
            assert script.get("hook") and script.get("beats")
            ledger.record("brain", model=mlabel, prompt_version=version, cost_usd=cost, item_id=item_id)
            return _revise_if_weak(None, script, topic, item_id)
        except Exception as e:
            ledger.record("brain", prompt_version=version, ok=False, detail=str(e), item_id=item_id)
    script = dict(random.choice(_DEMO)); script["topic"] = topic
    ledger.record("brain", model="demo-library", prompt_version="script_v1", cost_usd=0, item_id=item_id)
    return script


def _revise_if_weak(client, script, topic, item_id, threshold=7):
    """One critique pass: score the draft; if weak, rewrite once with the fix instruction."""
    if not ledger.budget_ok(EST_COST):
        return script
    try:
        cprompt, cver = config.load_prompt("critique_v1")
        cprompt = cprompt.replace("{script}", json.dumps(script))
        text, cost, mlabel = llm.chat(cprompt, max_tokens=300)
        verdict = json.loads(text[text.find("{"): text.rfind("}") + 1])
        ledger.record("critique", model=mlabel, prompt_version=cver, cost_usd=cost,
                      item_id=item_id, detail=f"score={verdict.get('score')}")
        if int(verdict.get("score", 10)) >= threshold:
            return script
        sprompt, sver = config.load_prompt("script_v3")
        sprompt = (sprompt.replace("{topic}", topic).replace("{cta_line}", CTA_LINE)
                   .replace("{editor_notes}", editor_notes())
                   + f"\n\nPrevious draft was rejected. Editor's instruction: {verdict.get('fix_instruction')}\nPrevious draft: {json.dumps(script)}")
        text2, cost2, mlabel2 = llm.chat(sprompt, max_tokens=800)
        revised = json.loads(text2[text2.find("{"): text2.rfind("}") + 1])
        assert revised.get("hook") and revised.get("beats")
        ledger.record("brain_revision", model=mlabel2, prompt_version=sver, cost_usd=cost2, item_id=item_id)
        return revised
    except Exception as e:
        ledger.record("critique", ok=False, detail=str(e), item_id=item_id)
        return script


def captions(script: dict, item_id=None) -> dict:
    """Ready-to-paste captions per platform. Claude (live) or template (dry-run)."""
    if llm.ready() and ledger.budget_ok(EST_COST):
        try:
            prompt, version = config.load_prompt("caption_v1")
            prompt = prompt.replace("{script}", json.dumps(script))
            text, cost, mlabel = llm.chat(prompt, max_tokens=500)
            caps = json.loads(text[text.find("{"): text.rfind("}") + 1])
            ledger.record("captions", model=mlabel, prompt_version=version, cost_usd=cost, item_id=item_id)
            return caps
        except Exception as e:
            ledger.record("captions", ok=False, detail=str(e), item_id=item_id)
    hook = script.get("hook", "One AI move you can use today.")
    beats = script.get("beats", [])
    value = beats[0]["text"] if beats else "A practical tool, in under a minute."
    caps = {"instagram": {"caption": f"{hook}\n{value}\nSave this for later.\n{script.get('cta', CTA_LINE)}",
                          "hashtags": ["aitools", "chatgpttips", "productivityhacks", "techtok", "learnai"]},
            "tiktok": {"caption": f"{hook} — wait for the tool.",
                       "hashtags": ["aitools", "techtok", "learnai", "productivity"],
                       "sound_note": "search a trending calm tech/lofi sound in-app and layer it low"},
            "youtube": {"title": hook[:90],
                        "description": f"{value} {script.get('cta', CTA_LINE)}",
                        "tags": ["ai tools", "chatgpt", "productivity", "ai tutorial", "tech tips", "learn ai"]}}
    ledger.record("captions", model="template", cost_usd=0, item_id=item_id)
    return caps


def editor_notes(limit=8) -> str:
    """Taste memory: your recent rejection reasons become standing instructions."""
    try:
        reasons = []
        for it in board.list("rejected")[-limit:]:
            rej = (it.get("payload") or {}).get("rejection") or {}
            if rej.get("reason"):
                reasons.append(rej["reason"])
        if not reasons:
            return "none yet"
        from collections import Counter
        return "; ".join(f"{r} (x{c})" for r, c in Counter(reasons).most_common(5))
    except Exception:
        return "none yet"


def hook_taste(limit=8) -> str:
    """Hooks you approved (or hand-picked in Studio) become style examples for future scripts."""
    try:
        liked = []
        for st in ("approved", "scheduled", "published", "reported"):
            for it in board.list(st)[-limit:]:
                h = ((it.get("payload") or {}).get("script") or {}).get("hook")
                if h:
                    liked.append(h)
        return "; ".join(f'"{h}"' for h in liked[-limit:]) or "none yet"
    except Exception:
        return "none yet"
