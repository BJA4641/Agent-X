"""brain.py v5.4 — scriptwriting with full context: brand docs + memory + trends + grader loop.
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

# v5.4 FIX: _DEMO_SCRIPT used to be hardcoded AI content (free ai tool nobody talks about)
# which fired whenever LLM failed → produced AI posts with #ai #tech on pet accounts.
# Now it uses niche-neutral placeholders; real niche is injected by _fallback_for_niche().
_DEMO_SCRIPT = {
    "hook": "stop scrolling.",
    "hooks": ["stop scrolling.", "wait till you see this.", "nobody talks about this."],
    "title": "you need to see this",
    "hashtags": ["viral", "fyp", "foryou", "foryoupage", "trending", "viralvideo", "reels", "shorts"],
    "caption": "save this for later 💡",
    "beats": [
      {"voiceover":"Stop scrolling.","on_screen_text":"STOP","visual_prompt":"high-contrast bold pattern-interrupt poster, vertical 9:16, brand colors","visual_source":"poster","camera":"hold","transition_in":"cut","transition_out":"zoom_punch","sfx":"boom","duration_ms":1200},
      {"voiceover":"Here is something most people miss.","on_screen_text":"MOST MISS THIS","visual_prompt":"relevant scene for the topic, cinematic lighting, vertical 9:16","visual_source":"broll","camera":"slow_push","transition_in":"zoom_punch","transition_out":"whip","sfx":"whoosh","duration_ms":4200},
      {"voiceover":"It takes 30 seconds and saves hours.","on_screen_text":"30 SEC","visual_prompt":"clean aesthetic b-roll matching topic, warm light, vertical 9:16","visual_source":"broll","camera":"slide_r","transition_in":"whip","transition_out":"flash_white","sfx":"pop","duration_ms":4500},
      {"voiceover":"Try it today.","on_screen_text":"TRY IT","visual_prompt":"hands in action, on-screen demo, vertical 9:16","visual_source":"broll","camera":"slow_push","transition_in":"flash_white","transition_out":"cut","sfx":"click","duration_ms":4200},
      {"voiceover":"Follow for more.","on_screen_text":"FOLLOW","visual_prompt":"clean end card with follow button, vertical 9:16","visual_source":"poster","camera":"hold","transition_in":"fade","transition_out":"cut","sfx":"riser","duration_ms":2800},
    ],
    "cta": CTA_LINE,
}


def write_script(topic: str, item_id=None, account_id=None, project_id=None,
                 grade_feedback: str = "") -> dict:
    """Write a script with full brand/memory/trend context and grade it.
    Rewrites up to grader.MAX_ATTEMPTS times if score < MIN_GRADE.

    v5.6 P0 FIX: accepts grade_feedback= from the job payload (CQO rewrite
    loop passes the grader's fix list). v5.5.1 creative.py passed this kwarg
    while brain.py did not accept it -> TypeError x7,220 -> 63h outage.
    Job-supplied feedback takes priority and is merged with memory feedback."""
    _job_feedback = (grade_feedback or "").strip()
    prompt_tpl, version = config.load_prompt("script_v3")
    brand = _load_brand_context(account_id)
    # v5.4: look up niche once so all fallbacks (hashtags/visuals/captions)
    #       are niche-correct — never again #ai on a cat post.
    account_niche = _niche_for_account(account_id)
    mem = memory.context_block(account_id, project_id)
    try:
        from . import scout
        trends = scout.recent_trends(5, niche=account_niche)
    except Exception:
        trends = "pattern_interrupt hooks · 6-7 beats · tight cuts · upbeat bed"
    grade_feedback = memory.load_grade_feedback(account_id, project_id) or ""
    if _job_feedback:
        # The CQO's concrete fix list for THIS rewrite outranks general memory.
        grade_feedback = (_job_feedback + "\n" + grade_feedback).strip()

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

    script = _normalize_script(script, topic, account_id=account_id, account_niche=account_niche)

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
            rewritten = _normalize_script(rewritten, topic, account_id=account_id, account_niche=account_niche)
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


# v5.4 FIX: signature now accepts account_id so hashtag/caption/visual defaults
#          can be niche-aware (no more #ai on pet posts).
def _normalize_script(raw: dict, topic: str, account_id=None, account_niche: str = "") -> dict:
    """Ensure every beat has all required fields."""
    if not isinstance(raw.get("beats"), list):
        raw["beats"] = []
    niche = (account_niche or _niche_for_account(account_id) or "").lower()
    new_beats = []
    for i, b in enumerate(raw["beats"]):
        if isinstance(b, str):
            b = {"voiceover": b}
        voice = b.get("voiceover") or b.get("text") or ""
        on_screen = b.get("on_screen_text") or _power_word(voice)
        visual_prompt = b.get("visual_prompt") or b.get("image_prompt") or _visual_prompt_for_niche(niche, i)
        new_beats.append({
            "voiceover": voice,
            "on_screen_text": str(on_screen)[:40],
            "visual_prompt": visual_prompt,
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
    if not raw.get("hashtags") or not isinstance(raw["hashtags"], list) or len(raw["hashtags"]) < 3:
        raw["hashtags"] = _hashtags_for_niche(niche)
    if not raw.get("caption"):
        raw["caption"] = _caption_for_niche(niche)
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
    """Per-platform captions from the script's caption/hashtags. Niche-aware fallback."""
    cap = script.get("caption","save this for later")
    niche = _niche_for_account(None, topic=script.get("title",""))
    tags = script.get("hashtags") or _hashtags_for_niche(niche)
    hook = script.get("hook","")
    sound_note = _sound_for_niche(niche)
    return {
      "instagram": {"caption": f"{cap}\n\n{hook}", "hashtags": tags},
      "tiktok":    {"caption": f"{hook} — {cap}",  "hashtags": tags[:8], "sound_note": sound_note},
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


# ============================================================
# v5.4 NICHE-LEVEL FALLBACKS — no more #ai on pet posts
# ============================================================

_NICHE_HASHTAGS = {
    "pets":       ["petsoftiktok", "catsoftiktok", "dogsoftiktok", "petlovers", "cutepets", "cats", "dogs", "rescuepet", "adoptdontshop", "petrescue", "kitten", "puppy", "fyp", "viral", "trending"],
    "cats":       ["catsoftiktok", "cats", "cutecats", "catlovers", "kitten", "meow", "catlife", "rescuecat", "fyp", "viral", "catlover", "kitty", "chonky", "blackcat", "orangecat"],
    "dogs":       ["dogsoftiktok", "dogs", "doglovers", "puppy", "doglife", "rescuedog", "goodboy", "fyp", "viral", "puppies", "doglover", "goldenretriever", "puppytok", "dailydog"],
    "fitness":    ["fitness", "gymtok", "workout", "gym", "fittok", "fitnessmotivation", "gymmotivation", "homeworkout", "fyp", "viral", "bodybuilding", "weightloss", "fit", "training", "gains"],
    "finance":    ["personalfinance", "financetok", "moneytok", "sidehustle", "financialfreedom", "investing", "budgeting", "savemoney", "makemoneyonline", "fyp", "viral", "moneytips", "passiveincome", "sidehustleideas", "wealth"],
    "cooking":    ["cooking", "foodtok", "recipe", "easyrecipe", "foodie", "homecooking", "quickrecipes", "foodlover", "cookingtiktok", "fyp", "viral", "asmrfood", "mealprep", "yummy", "budgetmeals"],
    "ai":         ["ai", "tech", "tools", "chatgpt", "productivity", "aitools", "techtok", "learnai", "aitips", "aiupdates", "viral", "fyp", "artificialintelligence", "aitech", "generativeai"],
    "tech":       ["tech", "techtok", "gadgets", "technology", "productivity", "techtips", "smartphone", "fyp", "viral", "innovation", "technews", "apps", "cooltech", "lifehack", "howto"],
    "beauty":     ["beauty", "makeup", "skincare", "beautytok", "makeuptutorial", "glowup", "skincareroutine", "makeuplook", "fyp", "viral", "beautyhacks", "makeuphacks", "skincaretips", "hairtok", "grwm"],
    "gaming":     ["gaming", "gametok", "videogames", "gamer", "gamingclips", "funnygaming", "xbox", "playstation", "pcgaming", "fyp", "viral", "gamermemes", "streamer", "esports", "gameplay"],
    "travel":     ["travel", "traveltok", "wanderlust", "travelbucketlist", "travelhacks", "cheapflights", "vacation", "fyp", "viral", "solotravel", "travelvlog", "hiddengem", "visit", "explore", "travellife"],
}

_SOUND_FOR_NICHE = {
    "pets":    "trending cute upbeat sound",
    "cats":    "trending cute/funny cat sound",
    "dogs":    "trending upbeat dog sound",
    "fitness": "trending hard-hitting gym beat",
    "finance": "trending upbeat lofi/hustle bed",
    "cooking": "trending cozy upbeat ASMR-friendly bed",
    "ai":      "trending upbeat lofi/tech",
    "tech":    "trending upbeat electronic",
    "beauty":  "trending pop/bedroom pop",
    "gaming":  "trending hip-hop / gaming edit sound",
    "travel":  "trending chill upbeat / tropical house",
}

_VISUAL_FOR_NICHE = {
    "pets":   ["cute pet close-up, soft natural light, vertical 9:16, heartwarming", "pet in funny or heartwarming moment, shallow depth of field, vertical 9:16", "cozy home scene with pet, warm tones, vertical 9:16"],
    "cats":   ["close-up of cat face with big eyes, soft window light, vertical 9:16", "cat doing funny thing, cozy home, warm light, vertical 9:16", "kitten playing with toy, high-speed, cute, vertical 9:16"],
    "dogs":   ["happy dog outdoors, golden hour, vertical 9:16", "dog playing fetch, sun-flare, action shot, vertical 9:16", "puppy close-up, big eyes, soft bokeh, vertical 9:16"],
    "fitness":["gym action shot, dramatic lighting, sweat, vertical 9:16", "before/after split, motivational, vertical 9:16", "home workout on mat, natural light, vertical 9:16"],
    "finance":["clean desk with laptop and coffee, morning light, vertical 9:16", "phone showing bank app / numbers, close-up, vertical 9:16", "person writing budget in notebook, vertical 9:16"],
    "cooking":["sizzling pan close-up, steam, warm kitchen light, vertical 9:16", "hands chopping veggies fast, ASMR-friendly, vertical 9:16", "finished plated dish, top-down hero shot, vertical 9:16"],
    "ai":     ["dark tech-noir neon cyan, laptop close-up, vertical 9:16", "AI interface floating in air, cinematic, vertical 9:16", "code on screen reflected in glasses, vertical 9:16"],
    "tech":   ["gadget unboxing, clean desk, soft light, vertical 9:16", "phone screen close-up, app demo, vertical 9:16", "multiple screens, moody tech lighting, vertical 9:16"],
    "beauty": ["makeup flat lay, ring light, pastel tones, vertical 9:16", "close-up face with makeup in progress, vertical 9:16", "skincare products arranged aesthetically, vertical 9:16"],
}


def _niche_for_account(account_id) -> str:
    """Look up the project_accounts.niche field. Never returns None."""
    if not account_id or not config.HAS_SUPABASE:
        return ""
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        r = sb.table("project_accounts").select("niche").eq("id", str(account_id)).limit(1).execute().data
        if r and r[0].get("niche"):
            n = str(r[0]["niche"]).lower().strip()
            # Normalize e.g. "pet rescue" -> "pets", "cat" -> "cats"
            for key in ("cats","cat","kitten","kitty"):
                if key in n: return "cats"
            for key in ("dogs","dog","puppy"):
                if key in n: return "dogs"
            for key in ("pet","animal","rescue"):
                if key in n: return "pets"
            for key in ("fitness","gym","workout"):
                if key in n: return "fitness"
            for key in ("financ","money","side hustle","wealth"):
                if key in n: return "finance"
            for key in ("cook","food","recipe","kitchen"):
                if key in n: return "cooking"
            for key in ("ai ","artificial intelligence","chatgpt"):
                if key in n: return "ai"
            for key in ("tech","gadget"):
                if key in n: return "tech"
            for key in ("beauty","makeup","skincare"):
                if key in n: return "beauty"
            for key in ("gaming","game"):
                if key in n: return "gaming"
            for key in ("travel","trip"):
                if key in n: return "travel"
            return n.split()[0]
    except Exception:
        pass
    return ""


def _hashtags_for_niche(niche: str) -> list:
    if not niche:
        return ["fyp", "foryou", "foryoupage", "viral", "trending", "viralvideo", "reels", "shorts"]
    return _NICHE_HASHTAGS.get(niche, ["fyp", "foryou", "viral", "trending", niche.replace(" ",""), niche+"tok", "shorts", "reels"])


def _caption_for_niche(niche: str) -> str:
    base = {
        "pets":   "save this for later 🐾 follow for more",
        "cats":   "save this for later 🐱 follow for more",
        "dogs":   "save this for later 🐶 follow for more",
        "fitness":"save this for later 💪 follow for more",
        "finance":"save this for later 💰 follow for more",
        "cooking":"save this for later 🍳 follow for more",
        "ai":     "save this for later · one AI move a day 💡",
        "tech":   "save this for later 🔧 follow for more",
        "beauty": "save this for later ✨ follow for more",
        "gaming": "save this for later 🎮 follow for more",
        "travel": "save this for later ✈️ follow for more",
    }
    return base.get(niche, "save this for later 💡 follow for more")


def _sound_for_niche(niche: str) -> str:
    return _SOUND_FOR_NICHE.get(niche, "trending upbeat sound")


def _visual_prompt_for_niche(niche: str, beat_idx: int) -> str:
    """Return a niche-appropriate fallback visual prompt when LLM doesn't give one."""
    if niche and niche in _VISUAL_FOR_NICHE:
        return _VISUAL_FOR_NICHE[niche][beat_idx % len(_VISUAL_FOR_NICHE[niche])]
    # Generic but on-brief (NOT "dark tech-noir" which assumes tech)
    generic = [
        "high-contrast bold pattern-interrupt poster, vertical 9:16, brand colors",
        "relevant scene for the topic, cinematic lighting, vertical 9:16",
        "clean aesthetic b-roll matching topic, warm light, vertical 9:16",
        "hands in action, on-screen demo, vertical 9:16",
        "clean end card with follow button, vertical 9:16",
    ]
    return generic[beat_idx % len(generic)]
