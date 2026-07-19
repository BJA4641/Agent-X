"""brain.py v3 — scriptwriting. Returns a full DIRECTOR'S SHOT LIST:
  {hook, hook_options, beats:[{voiceover, on_screen_text, visual_prompt, visual_source,
                               camera, transition_in, transition_out, sfx, duration_ms, text}],
   cta, hashtags, caption, title, total_ms}
Backward-compatible: falls back to demo scripts, accepts older {text, image_prompt} beats too.
"""
import json, random
from . import config, ledger, board, llm

CTA_LINE = config.get("CTA_LINE", "Follow for one move a day.")
EST_COST = 0.02

_DEMO_TOPIC = "AI tools"

_DEMO_SCRIPT = {
    "hook": "stop scrolling.",
    "hook_options": ["stop scrolling.", "delete this app.", "this is illegal."],
    "title": "free ai tool nobody talks about",
    "hashtags": ["ai","tech","tools","chatgpt","productivity","aitools","techtok","learnai","aitips","aiupdates"],
    "caption": "save this for later · one AI move a day 💡",
    "beats": [
      {"voiceover": "Stop scrolling.", "on_screen_text": "STOP", "visual_prompt": "high-contrast red pattern-interrupt poster, bold two-word typography, vertical 9:16",
       "visual_source": "poster", "camera": "hold", "transition_in": "cut", "transition_out": "zoom_punch", "sfx": "boom", "duration_ms": 1200},
      {"voiceover": "Your browser has a free AI you never opened.", "on_screen_text": "FREE AI", "visual_prompt": "extreme close-up of Chrome address bar, glowing AI button, dark tech-noir neon cyan, vertical 9:16",
       "visual_source": "ui_mockup", "camera": "slow_push", "transition_in": "zoom_punch", "transition_out": "whip", "sfx": "whoosh", "duration_ms": 4200},
      {"voiceover": "It summarizes any page without sending data out.", "on_screen_text": "PRIVATE", "visual_prompt": "laptop on clean desk with summary cards floating up from the browser window, soft studio light, vertical 9:16",
       "visual_source": "broll", "camera": "slide_r", "transition_in": "whip", "transition_out": "flash_white", "sfx": "pop", "duration_ms": 4500},
      {"voiceover": "Writers use it to fix tone in one click.", "on_screen_text": "1 CLICK", "visual_prompt": "hands typing on keyboard in warm lamp light, text morphing on screen, cinematic depth of field, vertical 9:16",
       "visual_source": "broll", "camera": "slow_push", "transition_in": "flash_white", "transition_out": "cut", "sfx": "click", "duration_ms": 4200},
      {"voiceover": "And it works offline on a plane.", "on_screen_text": "✈ OFFLINE", "visual_prompt": "airplane window seat at night, laptop glow on the tray table, cinematic bokeh, vertical 9:16",
       "visual_source": "broll", "camera": "tilt_up", "transition_in": "cut", "transition_out": "fade", "sfx": "none", "duration_ms": 3800},
      {"voiceover": "Follow for one AI move a day.", "on_screen_text": "FOLLOW", "visual_prompt": "dark rounded card with plus FOLLOW button, gradient background, brand end-card, vertical 9:16",
       "visual_source": "poster", "camera": "hold", "transition_in": "fade", "transition_out": "cut", "sfx": "riser", "duration_ms": 2800},
    ],
    "cta": CTA_LINE,
}

def write_script(topic: str, item_id=None) -> dict:
    if llm.ready() and ledger.budget_ok(EST_COST):
        prompt, version = config.load_prompt("script_v3")
        # Load brand docs for this account if available (passed via topic context)
        brand_docs = _load_brand_context(topic)
        prompt = (prompt.replace("{topic}", topic).replace("{cta_line}", CTA_LINE)
                  .replace("{editor_notes}", editor_notes()).replace("{liked_hooks}", hook_taste())
                  .replace("{tone_guide}", brand_docs.get("tone_guide",""))
                  .replace("{visual_rules}", brand_docs.get("visual_rules",""))
                  .replace("{content_rules}", brand_docs.get("content_rules","")))
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=1500)
            script = json.loads(text[text.find("{"): text.rfind("}") + 1])
            script = _normalize_script(script, topic)
            ledger.record("brain", model=mlabel, prompt_version=version, cost_usd=cost, item_id=item_id)
            return _revise_if_weak(None, script, topic, item_id)
        except Exception as e:
            ledger.record("brain", prompt_version=version, ok=False, detail=str(e)[:300], item_id=item_id)
    # Fallback — adapt demo script to the topic with simple substitution
    script = json.loads(json.dumps(_DEMO_SCRIPT))
    script["title"] = topic[:60]
    ledger.record("brain", model="demo-library-v3", cost_usd=0, item_id=item_id)
    return script


def _normalize_script(raw: dict, topic: str) -> dict:
    """Make sure every beat has all required fields, defaulting sensibly."""
    if not isinstance(raw.get("beats"), list):
        raw["beats"] = []
    # If beats are in old format {text, image_prompt}, up-convert
    new_beats = []
    for i, b in enumerate(raw["beats"]):
        if isinstance(b, str):
            b = {"voiceover": b}
        voice = b.get("voiceover") or b.get("text") or ""
        on_screen = b.get("on_screen_text") or _power_word(voice)
        new_beats.append({
            "voiceover": voice,
            "on_screen_text": str(on_screen)[:40],
            "visual_prompt": b.get("visual_prompt") or b.get("image_prompt") or "cinematic vertical 9:16 b-roll, dark tech-noir",
            "visual_source": b.get("visual_source") or ("poster" if i==0 else "broll"),
            "camera": b.get("camera") or "slow_push",
            "transition_in": b.get("transition_in") or ("cut" if i==0 else "zoom_punch"),
            "transition_out": b.get("transition_out") or "cut",
            "sfx": b.get("sfx") or "whoosh",
            "duration_ms": int(b.get("duration_ms") or 3500),
        })
    raw["beats"] = new_beats
    if not raw.get("hook"):
        raw["hook"] = (new_beats[0]["voiceover"] if new_beats else topic)[:60]
    if not raw.get("cta"):
        raw["cta"] = CTA_LINE
    if not raw.get("title"):
        raw["title"] = topic[:80]
    if not raw.get("hashtags") or not isinstance(raw["hashtags"], list):
        raw["hashtags"] = ["ai","tech","tools","productivity","aitools","techtok","learnai","aitips","aiupdates","viral"]
    if not raw.get("caption"):
        raw["caption"] = "save this · one move a day"
    # Hook beat (beat 0) should be a poster with very short on-screen text
    if new_beats:
        new_beats[0]["visual_source"] = "poster"
        new_beats[0]["on_screen_text"] = _power_word(raw["hook"])
        new_beats[0]["duration_ms"] = max(1000, min(1800, new_beats[0]["duration_ms"]))
        new_beats[0]["sfx"] = "boom"
    # Last beat = CTA end card
    if len(new_beats) >= 2:
        last = new_beats[-1]
        last["visual_source"] = "poster"
        last["on_screen_text"] = "FOLLOW"
        last["sfx"] = "riser"
        last["voiceover"] = raw["cta"]
        last["duration_ms"] = max(2500, min(last["duration_ms"], 3500))
    return raw


def _load_brand_context(topic: str) -> dict:
    """If topic is prefixed with account:<id>, pull brand docs from the DB so scripts obey them."""
    return {"tone_guide":"","visual_rules":"","content_rules":""}


def _revise_if_weak(client, script, topic, item_id, threshold=7):
    if not ledger.budget_ok(EST_COST): return script
    try:
        cprompt, cver = config.load_prompt("critique_v1")
        cprompt = cprompt.replace("{script}", json.dumps({k:script[k] for k in ("hook","beats","cta") if k in script}))
        text, cost, mlabel = llm.chat(cprompt, max_tokens=400)
        verdict = json.loads(text[text.find("{"): text.rfind("}") + 1])
        ledger.record("critique", model=mlabel, prompt_version=cver, cost_usd=cost, item_id=item_id,
                      detail="score=" + str(verdict.get("score")))
        if int(verdict.get("score",10)) >= threshold: return script
        sprompt, sver = config.load_prompt("script_v3")
        sprompt = (sprompt.replace("{topic}", topic).replace("{cta_line}", CTA_LINE)
                   .replace("{editor_notes}", editor_notes())
                   .replace("{liked_hooks}", hook_taste())
                   .replace("{tone_guide}","").replace("{visual_rules}","").replace("{content_rules}","")
                   + f"\n\nPrevious draft rejected. Editor note: {verdict.get('fix_instruction')}\nPrevious draft: {json.dumps(script)}")
        text2, cost2, mlabel2 = llm.chat(sprompt, max_tokens=1500)
        revised = json.loads(text2[text2.find("{"): text2.rfind("}") + 1])
        revised = _normalize_script(revised, topic)
        ledger.record("brain_revision", model=mlabel2, prompt_version=sver, cost_usd=cost2, item_id=item_id)
        return revised
    except Exception as e:
        ledger.record("critique", ok=False, detail=str(e)[:200], item_id=item_id)
        return script


def captions(script: dict, item_id=None) -> dict:
    """Per-platform captions from the script's caption/hashtags."""
    if llm.ready() and ledger.budget_ok(EST_COST/2):
        try:
            prompt, version = config.load_prompt("caption_v1")
            prompt = prompt.replace("{script}", json.dumps(script))
            text, cost, mlabel = llm.chat(prompt, max_tokens=600)
            caps = json.loads(text[text.find("{"): text.rfind("}") + 1])
            ledger.record("captions", model=mlabel, prompt_version=version, cost_usd=cost, item_id=item_id)
            return caps
        except Exception:
            pass
    cap = script.get("caption", "save this for later")
    tags = script.get("hashtags") or ["ai","tech","tools"]
    hook = script.get("hook", "")
    return {
      "instagram": {"caption": f"{cap}\n\n{hook}", "hashtags": tags},
      "tiktok":    {"caption": f"{hook} — {cap}",  "hashtags": tags[:8], "sound_note": "trending calm tech/lofi"},
      "youtube":   {"title": hook[:90], "description": f"{cap}\n\n{script.get('cta','')}",
                    "tags": tags[:10]},
    }


def editor_notes(limit=8) -> str:
    try:
        reasons = []
        for it in board.list("rejected")[-limit:]:
            r = (it.get("payload") or {}).get("rejection") or {}
            if r.get("reason"): reasons.append(r["reason"])
        if not reasons: return "none yet"
        from collections import Counter
        return "; ".join(f"{r} (x{c})" for r,c in Counter(reasons).most_common(5))
    except Exception:
        return "none yet"


def hook_taste(limit=8) -> str:
    try:
        liked = []
        for st in ("approved","scheduled","published","reported"):
            for it in board.list(st)[-limit:]:
                h = ((it.get("payload") or {}).get("script") or {}).get("hook")
                if h: liked.append(h)
        return "; ".join(f'"{h}"' for h in liked[-limit:]) or "none yet"
    except Exception:
        return "none yet"


def _power_word(text: str) -> str:
    stop = {"the","a","an","is","are","was","were","of","to","in","on","at","and","or","if",
            "you","your","i","me","my","we","us","our","it","its","this","that","for","with",
            "about","from","by","as","but","not","no","so","do","did","does","been","can","will"}
    words = [w.strip(".,!?:;\"'()[]{}").upper() for w in (text or "").split()]
    best, best_score = "", -1
    for w in words:
        if len(w) < 3 or w.lower() in stop: continue
        sc = len(w)
        if any(c.isdigit() or c in "$%#" for c in w): sc += 50
        if w in {"STOP","WAIT","NEVER","SECRET","FREE","INSTANTLY","CRAZY","HIDDEN"}: sc += 100
        if sc > best_score:
            best_score, best = sc, w
    return best or (words[0] if words else "WATCH")
