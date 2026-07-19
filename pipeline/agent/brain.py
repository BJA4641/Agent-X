"""brain.py v4.1 — scriptwriting with full context: brand docs + memory + trends + grader loop.
Returns a full DIRECTOR'S SHOT LIST:
  {hook, hooks[], beats:[{voiceover, on_screen_text, visual_prompt, visual_source,
                          camera, transition_in, transition_out, sfx, duration_ms}],
   cta, hashtags, caption, title, total_ms, grade}
Backward-compatible with older {text,image_prompt} beats.
"""
import json
from . import config, ledger, board, llm, grader as grader_mod
try:
    from . import memory
except Exception as _e:
    print(f"[brain] WARNING: memory import failed ({_e}); using no-op stub.")
    from . import _memstub
    memory = _memstub.MemoryStub()

CTA_LINE = config.get("CTA_LINE", "Follow for one move a day.")
EST_COST = 0.025

_DEMO_SCRIPT = {
    "hook": "stop scrolling.",
    "hooks": ["stop scrolling.", "delete this app.", "this is illegal."],
    "title": "free ai tool nobody talks about",
    "hashtags": ["ai","tech","tools","chatgpt","productivity","aitools","techtok","learnai","aitips","aiupdates"],
    "caption": "save this for later · one AI move a day 💡",
    "beats": [
      {"voiceover":"Stop scrolling.","on_screen_text":"STOP","visual_prompt":"high-contrast red pattern-interrupt poster, bold two-word typography, vertical 9:16",
       "visual_source":"poster","camera":"hold","transition_in":"cut","transition_out":"zoom_punch","sfx":"boom","duration_ms":1200},
      {"voiceover":"Your browser has a free AI you never opened.","on_screen_text":"FREE AI","visual_prompt":"extreme close-up of Chrome address bar, glowing AI button, dark tech-noir neon cyan, vertical 9:16",
       "visual_source":"ui_mockup","camera":"slow_push","transition_in":"zoom_punch","transition_out":"whip","sfx":"whoosh","duration_ms":4200},
      {"voiceover":"It summarizes any page without sending data out.","on_screen_text":"PRIVATE","visual_prompt":"laptop on clean desk, summary cards floating from browser, soft studio light, vertical 9:16",
       "visual_source":"broll","camera":"slide_r","transition_in":"whip","transition_out":"flash_white","sfx":"pop","duration_ms":4500},
      {"voiceover":"Writers fix tone in one click.","on_screen_text":"1 CLICK","visual_prompt":"hands typing in warm lamp light, text morphing on screen, cinematic depth of field, vertical 9:16",
       "visual_source":"broll","camera":"slow_push","transition_in":"flash_white","transition_out":"cut","sfx":"click","duration_ms":4200},
      {"voiceover":"And it works offline on a plane.","on_screen_text":"✈ OFFLINE","visual_prompt":"airplane window seat at night, laptop glow on tray, cinematic bokeh, vertical 9:16",
       "visual_source":"broll","camera":"tilt_up","transition_in":"cut","transition_out":"fade","sfx":"none","duration_ms":3800},
      {"voiceover":"Follow for one AI move a day.","on_screen_text":"FOLLOW","visual_prompt":"dark rounded card with FOLLOW button, gradient background, brand end-card, vertical 9:16",
       "visual_source":"poster","camera":"hold","transition_in":"fade","transition_out":"cut","sfx":"riser","duration_ms":2800},
    ],
    "cta": CTA_LINE,
}


def write_script(topic: str, item_id=None, account_id=None, project_id=None) -> dict:
    """Write a script with full brand/memory/trend context and grade it.
    Rewrites up to grader.MAX_ATTEMPTS times if score < MIN_GRADE."""
    prompt_tpl, version = config.load_prompt("script_v3")
    brand = _load_brand_context(account_id)
    mem = memory.context_block(account_id, project_id)
    try:
        from . import scout
        trends = scout.recent_trends(5)
    except Exception:
        trends = "pattern_interrupt hooks · 6-7 beats · tight cuts · upbeat bed"
    grade_feedback = memory.load_grade_feedback(account_id, project_id)

    def _fill(extra_note: str = "") -> str:
        # Brand docs: new 13-doc system maps to legacy placeholder names.
        exec_sum = brand.get("executive_summary", brand.get("business_plan",""))
        brand_id  = brand.get("brand_identity", brand.get("brand_guidelines",""))
        vis_id    = brand.get("visual_identity", brand.get("visual_rules",""))
        c_rules   = brand.get("content_rules","")
        ht_seo    = brand.get("hashtags_seo","")
        tt_pb     = brand.get("tiktok_playbook","")
        prod_sop  = brand.get("production_sop","")
        return (prompt_tpl
                .replace("{topic}", topic)
                .replace("{cta_line}", CTA_LINE)
                .replace("{editor_notes}", editor_notes())
                .replace("{liked_hooks}", hook_taste())
                .replace("{memory_block}", mem[:2500])
                .replace("{trends_block}", trends[:2000])
                .replace("{grade_feedback}", grade_feedback or "none yet")
                .replace("{tone_guide}", brand_id[:1500])
                .replace("{visual_rules}", vis_id[:1500])
                .replace("{content_rules}", (c_rules + "\n\n" + prod_sop)[:2000])
                .replace("{business_plan}", exec_sum[:1500])
                .replace("{brand_guidelines}", brand_id[:1500])
                # Extra injection the template may or may not use (graceful)
                .replace("{hashtags_seo}", ht_seo[:800])
                .replace("{tiktok_playbook}", tt_pb[:800])
                .replace("{production_sop}", prod_sop[:800])
                + extra_note)

    script = None
    final_verdict = None

    if llm.ready() and ledger.budget_ok(EST_COST):
        try:
            text, cost, mlabel = llm.chat(_fill(), max_tokens=1800)
            script = json.loads(text[text.find("{"): text.rfind("}")+1])
            ledger.record("brain", model=mlabel, prompt_version=version, cost_usd=cost, item_id=item_id)
        except Exception as e:
            ledger.record("brain", prompt_version=version, ok=False, detail=str(e)[:300], item_id=item_id)

    if not script:
        script = json.loads(json.dumps(_DEMO_SCRIPT))
        script["title"] = topic[:60]

    script = _normalize_script(script, topic)

    # === GRADER LOOP ===
    attempts = 0
    verdict = grader_mod.grade_post(script, account_id=account_id, project_id=project_id,
                                     item_id=item_id, brand_context=brand)
    final_verdict = verdict
    while not verdict["passed"] and attempts < grader_mod.MAX_ATTEMPTS:
        attempts += 1
        ledger.record("brain", model=mlabel if 'mlabel' in dir() else "llm",
                      cost_usd=0.025, item_id=item_id,
                      detail=f"rewrite_attempt_{attempts}_grade={verdict['overall']}")
        # Ask for a rewritten script using grader feedback
        rewritten = grader_mod.rewrite_script(script, verdict, topic,
                                              account_id=account_id, project_id=project_id,
                                              brand_context=brand)
        try:
            rewritten = _normalize_script(rewritten, topic)
            # Sanity: only accept rewrite if it has beats
            if rewritten.get("beats") and len(rewritten["beats"]) >= 4:
                script = rewritten
            verdict = grader_mod.grade_post(script, account_id=account_id, project_id=project_id,
                                             item_id=item_id, brand_context=brand)
            final_verdict = verdict
        except Exception as e:
            ledger.record("brain_rewrite", ok=False, detail=str(e)[:200], item_id=item_id)
            break

    script["grade"] = {
        "overall": final_verdict["overall"],
        "passed": final_verdict["passed"],
        "scores": final_verdict["scores"],
        "notes": final_verdict["notes"],
        "fix": final_verdict["fix"],
        "rewrites": attempts,
    }
    if not final_verdict["passed"]:
        script["grade"]["failed_reason"] = final_verdict["fix"]
        memory.add(account_id=account_id, role="brain",
                   content=f"Script FAILED grading after {attempts} rewrites — overall {final_verdict['overall']}/10. Needs manual review.",
                   metadata={"grade": final_verdict["overall"], "topic": topic[:80]})
    else:
        memory.add(account_id=account_id, role="brain",
                   content=f"Script PASSED grading: {final_verdict['overall']}/10 on '{topic[:60]}'.",
                   metadata={"grade": final_verdict["overall"], "topic": topic[:80]})
    return script


def _load_brand_context(account_id=None) -> dict:
    """Pull brand docs (new 13-doc set, with legacy aliases) for the writer."""
    empty = {k: "" for k in (
      "business_plan","brand_guidelines","tone_guide","visual_rules","content_rules",
      "executive_summary","vision_mission","revenue_model","brand_identity",
      "visual_identity","marketing_strategy","instagram_playbook","tiktok_playbook",
      "youtube_playbook","content_calendar","hashtags_seo","production_sop")}
    if not account_id or not config.HAS_SUPABASE:
        return empty
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        rows = (sb.table("account_documents").select("doc_type,content")
                .eq("account_id", account_id).execute().data or [])
        out = dict(empty)
        for r in rows:
            out[r["doc_type"]] = r.get("content") or ""
        # Backfill legacy aliases from new docs (so old templates still read something)
        if not out["business_plan"]:     out["business_plan"]     = out["executive_summary"]
        if not out["brand_guidelines"]:  out["brand_guidelines"]  = out["brand_identity"]
        if not out["tone_guide"]:        out["tone_guide"]        = out["brand_identity"]
        if not out["visual_rules"]:      out["visual_rules"]      = out["visual_identity"]
        return out
    except Exception:
        return empty


def _normalize_script(raw: dict, topic: str) -> dict:
    """Ensure every beat has all required fields."""
    if not isinstance(raw.get("beats"), list):
        raw["beats"] = []
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
    # Hook: support "hooks" array or "hook" string
    if not raw.get("hook"):
        if raw.get("hooks") and isinstance(raw["hooks"], list):
            raw["hook"] = raw["hooks"][0]
        else:
            raw["hook"] = (new_beats[0]["voiceover"] if new_beats else topic)[:60]
    if raw.get("hooks") and isinstance(raw["hooks"], list) and raw["hooks"]:
        # use first hook if no explicit hook
        if not raw.get("hook") or raw["hook"] == raw.get("title"):
            raw["hook"] = raw["hooks"][0]
    if not raw.get("cta"):
        raw["cta"] = CTA_LINE
    if not raw.get("title"):
        raw["title"] = topic[:80]
    if not raw.get("hashtags") or not isinstance(raw["hashtags"], list):
        raw["hashtags"] = ["ai","tech","tools","productivity","aitools","techtok","learnai","aitips","aiupdates","viral"]
    if not raw.get("caption"):
        raw["caption"] = "save this · one move a day"
    if new_beats:
        new_beats[0]["visual_source"] = "poster"
        new_beats[0]["on_screen_text"] = _power_word(raw["hook"])
        new_beats[0]["duration_ms"] = max(1000, min(1800, new_beats[0]["duration_ms"]))
        new_beats[0]["sfx"] = "boom"
    if len(new_beats) >= 2:
        last = new_beats[-1]
        last["visual_source"] = "poster"
        last["on_screen_text"] = "FOLLOW"
        last["sfx"] = "riser"
        last["voiceover"] = raw["cta"]
        last["duration_ms"] = max(2500, min(last["duration_ms"], 3500))
    return raw


def captions(script: dict, item_id=None) -> dict:
    """Per-platform captions from the script's caption/hashtags."""
    cap = script.get("caption","save this for later")
    tags = script.get("hashtags") or ["ai","tech","tools"]
    hook = script.get("hook","")
    return {
      "instagram": {"caption": f"{cap}\n\n{hook}", "hashtags": tags},
      "tiktok":    {"caption": f"{hook} — {cap}",  "hashtags": tags[:8], "sound_note": "trending upbeat lofi/tech"},
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
        if w in {"STOP","WAIT","NEVER","SECRET","FREE","INSTANTLY","CRAZY","HIDDEN","DELETE","ILLEGAL"}: sc += 100
        if sc > best_score:
            best_score, best = sc, w
    return best or (words[0] if words else "WATCH")
