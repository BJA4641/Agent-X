"""departments/creative.py — D (Creative).

write_script: uses brain.write_script (v4.3, with grader loop INLINE the first
              draft), then hands the result to CQO for centralized grading.
render:      runs orchestrator.produce's render pipeline (voice + visuals +
              composer + captions) on a passed script, outputting a final mp4
              at output/<id>.mp4. Sends to post-production for polish.
"""
from __future__ import annotations
import os, time, json, traceback
from agentcore import Worker, Job, AgentContext, Priority, FatalError
from ..common import (board_patch_payload, board_get, OUTPUT_DIR,
                      brand_context_for, job_of, load_account)


def register(w: Worker):
    w.register("creative.write_script", write_script)
    w.register("creative.render",       render)
    w.register("creative.render_video", render_video)
    w.register("creative.write_carousel",  write_carousel)
    w.register("creative.render_carousel", render_carousel)


def _account_geo(sb, account_id):
    """v5.8: (geos, language) from project_accounts.config — cheap, cached-free."""
    try:
        if sb and account_id:
            res = (sb.table("project_accounts").select("config")
                   .eq("id", str(account_id)).execute())
            cfg = ((res.data or [{}])[0] or {}).get("config") or {}
            return (cfg.get("target_geos") or [], cfg.get("language") or "en")
    except Exception:
        pass
    return ([], "en")


# --------------------------------------------------------- render_video (AI video — fal/kling/veo)

def render_video(w: Worker, job: Job, ctx: AgentContext):
    """AI-generated video via aisuite (fal/kling/veo/sora). Expensive (~$0.10-0.40)
    so heavily CEO-gated. Falls back gracefully if no video key is set.

    Payload: { item_id, script, hook_image_path? (for image-to-video), topic? }
    """
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    script = job.payload.get("script") or {}
    account_id = job.account_id
    project_id = job.project_id
    topic = script.get("title") or job.payload.get("topic") or "content"

    # CEO gate — video is EXPENSIVE, so strict
    from ..common import kill_switch, ceo_decide, hard_budget_ok, remaining_budget
    if kill_switch():
        bus.agent("video", "⏸ kill switch on — video held", "warn", "video_held", job_id=job.id)
        w.queue.complete(job, {"ok": False, "paused": True})
        return
    if sb:
        d = ceo_decide(sb, "render_video", account_id=account_id, est_cost=0.15,
                       department="creative", topic=topic, item_id=item_id)
        if d["decision"] != "approve":
            bus.agent("ceo", f"👔 CEO video decision={d['decision']}: {d['reason']}", "warn",
                      f"ceo_video_{d['decision']}", job_id=job.id)
            # Fallback: hand off to regular render (static-image reel) which is cheaper
            if d["decision"] in ("deny", "cheaper", "delay"):
                bus.agent("video", "🎬 falling back to static-image reel (ffmpeg)", "info",
                          "video_fallback", job_id=job.id)
                job_of(w, "creative.render",
                       {"item_id": item_id, "script": script, "style": job.payload.get("style","cinemagraph")},
                       parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
                w.queue.complete(job, {"ok": True, "fallback": "static_render", "reason": d["reason"]})
                return
            if d["decision"] == "reuse":
                try:
                    asset_row = sb.table("asset_library").select("content").eq("id", d["reuse"]).limit(1).execute().data
                    if asset_row and __import__("os").path.exists(asset_row[0]["content"]):
                        job_of(w, "post.polish",
                               {"item_id": item_id, "video_path": asset_row[0]["content"], "script": script},
                               parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
                        w.queue.complete(job, {"ok": True, "reused": d["reuse"]})
                        return
                except Exception:
                    pass
                # reuse didn't resolve — fallback
                job_of(w, "creative.render",
                       {"item_id": item_id, "script": script},
                       parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
                w.queue.complete(job, {"ok": True, "fallback": "static_render"})
                return

    if not hard_budget_ok(next_cost_usd=0.15):
        bus.agent("cfo", f"⏸ budget too low for AI video (${remaining_budget():.3f}) — static fallback",
                  "warn", "video_budget", job_id=job.id)
        job_of(w, "creative.render",
               {"item_id": item_id, "script": script},
               parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
        w.queue.complete(job, {"ok": True, "fallback": "static_render"})
        return

    bus.agent("video", "🎥 generating AI video (fal/kling/veo)…", "info", "video_start",
              job_id=job.id, item_id=item_id)

    short_id = (item_id or job.id)[:8]
    out_vid = os.path.join(OUTPUT_DIR, short_id + "_ai.mp4")

    try:
        from agentcore import aisuite
        prompt = _assemble_narration(script) or topic
        img_bytes = None
        hook_img = job.payload.get("hook_image_path")
        if hook_img and os.path.exists(hook_img):
            with open(hook_img, "rb") as f:
                img_bytes = f.read()
        vid_path = aisuite.generate_video(prompt, image_bytes=img_bytes)
        if vid_path and os.path.exists(vid_path):
            import shutil
            shutil.copy(vid_path, out_vid)
            bus.agent("video", f"🎥 AI video ready: {os.path.getsize(out_vid)/1024/1024:.1f}MB",
                      "success", "video_done", job_id=job.id, item_id=item_id)
        else:
            raise RuntimeError("aisuite returned no path")
    except Exception as e:
        traceback.print_exc()
        bus.agent("video", f"🎥 AI video failed ({str(e)[:120]}) — falling back to static reel",
                  "warn", "video_fail", job_id=job.id)
        job_of(w, "creative.render",
               {"item_id": item_id, "script": script},
               parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
        w.queue.complete(job, {"ok": True, "fallback": "static_render", "error": str(e)[:200]})
        return

    # SEO (reuse creative's SEO path)
    plat_captions = {}
    seo_pack = {}
    try:
        from agent import brain as _brain
        _geos, _lang = _account_geo(sb, account_id)
        plat_captions = _brain.captions(script, item_id=item_id, geos=_geos, language=_lang, account_id=account_id)
    except Exception:
        pass
    try:
        from agent import seo as _seo
        seo_pack = _seo.seoize(topic, script, account_id=account_id,
                               project_id=project_id, captions=plat_captions, item_id=item_id) or {}
    except Exception:
        pass

    if sb and item_id:
        board_patch_payload(sb, item_id, {"video_path": out_vid, "script": script,
                                          "captions": plat_captions, "seo": seo_pack,
                                          "ai_video": True})

    caption_text = _compose_caption(plat_captions, seo_pack, script)
    job_of(w, "post.polish", {
        "item_id": item_id, "video_path": out_vid, "script": script,
        "captions": plat_captions, "seo": seo_pack, "caption_text": caption_text,
    }, parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
    w.queue.complete(job, {"ok": True, "video_path": out_vid, "ai_video": True})


# --------------------------------------------------------- write_script

def write_script(w: Worker, job: Job, ctx: AgentContext):
    from agent import brain as _brain, grader as _g, memory as _mem
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    topic = job.payload.get("topic", "")
    account_id = job.account_id or job.payload.get("account_id")
    project_id = job.project_id or job.payload.get("project_id")
    rewrite = int(job.payload.get("rewrite_attempt", 0))

    if not topic:
        w.fail_job(job, "creative.write_script: no topic", fatal=True)
        return

    # v5.5 CEO GATE: ask CEO before spending any money
    from ..common import kill_switch, hard_budget_ok, remaining_budget, ceo_decide
    if kill_switch():
        bus.agent("brain", "⏸ kill switch on — write held", "warn", "script_held",
                  job_id=job.id, item_id=item_id)
        w.queue.complete(job, {"ok": False, "paused": True})
        return
    # CEO decision
    if sb:
        d = ceo_decide(sb, "write_script", account_id=account_id, est_cost=0.04,
                       department="creative", topic=topic, item_id=item_id)
        if d["decision"] == "deny":
            bus.agent("ceo", f"👔 CEO denied: {d['reason']}", "warn", "ceo_deny", job_id=job.id)
            w.queue.complete(job, {"ok": False, "denied": d["reason"]})
            return
        if d["decision"] == "delay":
            bus.agent("ceo", f"👔 CEO delay: {d['reason']}", "warn", "ceo_delay", job_id=job.id)
            w.queue._update_row(job, {"status":"queued","scheduled_for":time.time()+3600,"error":d["reason"]})
            return
        if d["decision"] == "reuse":
            bus.agent("ceo", f"♻️ CEO reuse asset: {d.get('reuse')}", "info", "ceo_reuse", job_id=job.id)
            # Load reusable script & continue as if we wrote it
            try:
                asset_row = sb.table("asset_library").select("content").eq("id", d["reuse"]).limit(1).execute().data
                if asset_row:
                    script = json.loads(asset_row[0]["content"])
                    # skip the LLM write below
                    if sb and item_id:
                        board_patch_payload(sb, item_id, {"script": script, "reused_from": d["reuse"]})
                    # enqueue grade
                    from ..common import job_of
                    w.queue.enqueue(job_of(w, "cqo.grade_script", {"item_id": item_id, "account_id": account_id}, parent=job, priority=Priority.HIGH))
                    w.queue.complete(job, {"ok": True, "reused": d["reuse"]})
                    return
            except Exception: pass
    # Legacy budget check (belt-and-suspenders)
    if not hard_budget_ok(next_cost_usd=0.05):
        bus.agent("cfo", f"⏸ budget too low for script (${remaining_budget():.3f} left) — delaying",
                  "warn", "script_budget", job_id=job.id)
        w.queue._update_row(job, {"status": "queued", "scheduled_for": time.time() + 3600,
                                  "error": f"budget delay: ${remaining_budget():.3f} left"})
        return

    bus.agent("brain", f"✍️ writing draft {rewrite+1}: \"{topic[:70]}\"", "info",
              "script_start", job_id=job.id, item_id=item_id)

    try:
        script = _brain.write_script(
            topic, item_id=item_id, account_id=account_id, project_id=project_id,
            grade_feedback=job.payload.get("grade_feedback", ""),
        )
    except Exception as e:
        traceback.print_exc()
        w.fail_job(job, f"brain.write_script failed: {e}", fatal=False)
        return

    if not script or not script.get("beats"):
        w.fail_job(job, "brain returned empty script", fatal=True)
        return

    # Persist first (or rewrite) to board
    if sb and item_id:
        board_patch_payload(sb, item_id, {
            "script": script,
            "last_rewrite": rewrite,
        })

    # Hand to CQO
    bus.agent("brain", f"✍️ draft ready — {len(script.get('beats',[]))} beats, "
                       f"hook: \"{(script.get('hook') or '')[:50]}\"", "success",
              "script_done", job_id=job.id, item_id=item_id)
    job_of(w, "cqo.grade_script", {
        "item_id": item_id, "topic": topic, "script": script,
        "rewrite_attempt": rewrite,
    }, parent=job, account_id=account_id, project_id=project_id,
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "beats": len(script.get("beats",[])),
                           "hook": script.get("hook","")[:80]})


# --------------------------------------------------------- render

def render(w: Worker, job: Job, ctx: AgentContext):
    """Render video from an ALREADY-GRADED script. Reuses the legacy produce()
    pipeline's render steps (voice/visuals/composer/captions) but we OWN the
    flow here so we control retries/cost and never loop forever."""
    from agent import (voice as _voice, visuals as _v, captions as _cap,
                       overlays as _ov, music as _music, sfx as _sfx,
                       composer as _comp, captions as _capmod)
    from PIL import Image, ImageFilter
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    script = job.payload.get("script") or {}
    style = _v.pick_style(item_id, job.payload.get("style"))
    account_id = job.account_id
    project_id = job.project_id
    topic = script.get("title") or job.payload.get("topic") or "content"

    # v5.5 CEO GATE: ask CEO before spending money on render (~$0.02-0.06 for Gemini images)
    from ..common import kill_switch, hard_budget_ok, remaining_budget, ceo_decide
    if kill_switch():
        bus.agent("composer", "⏸ kill switch on — render held", "warn", "render_held",
                  job_id=job.id, item_id=item_id)
        w.queue.complete(job, {"ok": False, "paused": True})
        return
    if sb:
        d = ceo_decide(sb, "render_image", account_id=account_id, est_cost=0.03,
                       department="creative", topic=topic, item_id=item_id)
        if d["decision"] == "deny":
            bus.agent("ceo", f"👔 CEO denied render: {d['reason']}", "warn", "ceo_deny_render", job_id=job.id)
            w.queue.complete(job, {"ok": False, "denied": d["reason"]})
            return
        if d["decision"] == "delay":
            bus.agent("ceo", f"👔 CEO delay render: {d['reason']}", "warn", "ceo_delay_render", job_id=job.id)
            w.queue._update_row(job, {"status":"queued","scheduled_for":time.time()+3600,"error":d["reason"]})
            return
        if d["decision"] == "reuse":
            bus.agent("ceo", f"♻️ CEO reuse render asset: {d.get('reuse')}", "info", "ceo_reuse_render", job_id=job.id)
            # For now skip render entirely — mark item as needing repurpose of existing
            try:
                asset_row = sb.table("asset_library").select("content").eq("id", d["reuse"]).limit(1).execute().data
                if asset_row:
                    reused_path = asset_row[0]["content"]
                    if reused_path and __import__("os").path.exists(reused_path):
                        board_patch_payload(sb, item_id, {"video_path": reused_path, "reused_from": d["reuse"]})
                        job_of(w, "post.polish", {"item_id": item_id, "video_path": reused_path, "script": script},
                               parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
                        w.queue.complete(job, {"ok": True, "reused": d["reuse"]})
                        return
            except Exception:
                pass
    # Legacy budget check (belt-and-suspenders)
    if not hard_budget_ok(next_cost_usd=0.03):
        bus.agent("cfo", f"⏸ budget too low for render (${remaining_budget():.3f} left) — delaying 1h",
                  "warn", "render_budget", job_id=job.id)
        w.queue._update_row(job, {"status": "queued", "scheduled_for": time.time() + 3600,
                                  "error": f"render budget delay: ${remaining_budget():.3f} left"})
        return

    bus.agent("composer", f"🎬 rendering — style: {style}", "info", "render_start",
              job_id=job.id, item_id=item_id)

    if not script.get("beats"):
        w.fail_job(job, "render: no beats in script", fatal=True)
        return

    short_id = (item_id or job.id)[:8]
    vid = os.path.join(OUTPUT_DIR, short_id + ".mp4")
    audio = os.path.join(OUTPUT_DIR, short_id + ".mp3")

    try:
        beats = script.get("beats") or []
        cta = script.get("cta") or "Follow for more."
        hook_word = _hook_word(script.get("hook") or topic)
        total_beats = len(beats) + 1

        # 1) narration — v5.5 CEO gate for TTS spend
        narration = _assemble_narration(script)
        _tts_allowed = True
        if sb:
            td = ceo_decide(sb, "tts", account_id=account_id, est_cost=0.005,
                            department="creative", topic=topic, item_id=item_id)
            if td["decision"] in ("deny", "delay"):
                bus.agent("ceo", f"👔 CEO TTS delay: {td['reason']} — using silent captions-only reel",
                          "warn", "ceo_tts_delay", job_id=job.id)
                _tts_allowed = False
        if _tts_allowed:
            bus.agent("voice", "🎙️ recording narration…", "info", "voice_start",
                      job_id=job.id, item_id=item_id)
            try:
                words = _capmod.timed_words(narration, audio, item_id=item_id, style=style)
                _engine = getattr(_capmod, "LAST_ENGINE", "edge")
                bus.agent("voice", f"🎙️ narration recorded — {len(words)} words via {_engine}", "success",
                          "voice_done", job_id=job.id, item_id=item_id)
                # v5.6 quality metadata: which engine actually narrated. Batch 3's
                # quality floor reads this to route fallback-voice reels to review.
                if sb and item_id:
                    try:
                        board_patch_payload(sb, item_id, {"voice_engine": _engine})
                    except Exception:
                        pass
            except Exception as e:
                bus.agent("voice", f"🎙️ TTS failed, falling back to captions-only: {str(e)[:100]}",
                          "warn", "voice_fail", job_id=job.id)
                words = [{"word": w, "start": i*0.3, "end": (i+1)*0.3}
                         for i, w in enumerate(narration.split()[:60])]
                # create empty audio placeholder
                open(audio, "wb").close()
        else:
            # Captions-only fallback (no narration audio)
            words = [{"word": w, "start": i*0.3, "end": (i+1)*0.3}
                     for i, w in enumerate(narration.split()[:60])]
            open(audio, "wb").close()

        # 2) frames
        bus.agent("visuals", f"🎨 rendering {total_beats} frames…", "info",
                  "frames_start", job_id=job.id, item_id=item_id)
        frames = []
        hook_frame = os.path.join(OUTPUT_DIR, short_id + "_hook.jpg")
        _v.hook_poster_frame(hook_word, hook_frame, item_id=item_id, style=style)
        try:
            h = Image.open(hook_frame).convert("RGB")
            _ov.decorate_frame(h, hook_word, 0, total_beats, style,
                               is_hook=True, is_cta=False, hook_word=hook_word)
            h.save(hook_frame, quality=92)
        except Exception as e:
            print(f"[creative] hook frame error: {e}")
        frames.append(hook_frame)

        body_beats = beats[:-1] if len(beats) >= 2 else beats
        for i, beat in enumerate(body_beats, start=1):
            f = os.path.join(OUTPUT_DIR, f"{short_id}_b{i-1}.jpg")
            beat_text = beat.get("voiceover") or beat.get("text") or ""
            beat_prompt = beat.get("visual_prompt") or beat.get("image_prompt") or ""
            try:
                _v.beat_frame(beat_text, beat_prompt, f, seed=i-1, item_id=item_id,
                              style=style, beat_idx=i, total_beats=total_beats,
                              hook_word=hook_word, cta_text=cta)
            except Exception as e:
                print(f"[creative] beat {i} frame error: {e}")
                _v.beat_frame(beat_text, "", f, seed=i-1, item_id=item_id, style=style,
                              beat_idx=i, total_beats=total_beats, hook_word=hook_word,
                              cta_text=cta)
            frames.append(f)

        cta_frame = os.path.join(OUTPUT_DIR, short_id + "_cta.jpg")
        try:
            if len(frames) >= 2:
                bg = (Image.open(frames[-1]).convert("RGB").resize((1080,1920))
                      .filter(ImageFilter.GaussianBlur(28)))
            else:
                bg = Image.new("RGB", (1080,1920), (10,12,28))
            _ov.decorate_frame(bg, cta, total_beats-1, total_beats, style,
                               is_hook=False, is_cta=True, cta_text=cta)
            bg.save(cta_frame, quality=92)
            frames.append(cta_frame)
        except Exception as e:
            print(f"[creative] cta frame error: {e}")
            _v.beat_frame(cta, "", cta_frame, seed=99, item_id=item_id, style=style,
                          beat_idx=total_beats-1, total_beats=total_beats,
                          hook_word=hook_word, cta_text=cta)
            frames.append(cta_frame)
        bus.agent("visuals", f"🎨 {len(frames)} frames ready", "success",
                  "frames_done", job_id=job.id, item_id=item_id)

        # 3) captions
        bus.agent("composer", "💬 kinetic captions…", "info", "captions_start",
                  job_id=job.id, item_id=item_id)
        ass = os.path.join(OUTPUT_DIR, short_id + ".ass")
        chunks = _capmod.chunk_words(words, max_words=3, max_chars=20)
        a_dur = _audio_duration(audio)
        _capmod.write_ass(chunks, ass, total_dur=max(a_dur, 12.0))
        bus.agent("composer", f"💬 {len(chunks)} caption chunks", "success",
                  "captions_done", job_id=job.id, item_id=item_id)

        # 4) music + sfx
        bed = _music.for_item(item_id or short_id, max(a_dur, 15.0), OUTPUT_DIR)
        sfx_paths = []
        for k in range(len(frames) - 1):
            s = _sfx.for_cut(k, OUTPUT_DIR)
            if s:
                sfx_paths.append(s)

        # 5) final assemble
        bus.agent("composer", "🎬 final assembly…", "info", "edit_start",
                  job_id=job.id, item_id=item_id)
        per = max(2.4, a_dur/max(len(frames),1)) if a_dur > 0 else 3.0
        _comp.assemble(frames, audio, vid, narration_words=words, ass_path=ass,
                       per_beat=per, music_path=bed, sfx_paths=sfx_paths)
        bus.agent("composer", "🎬 video ready (9:16, captions, sound design)",
                  "success", "edit_done", job_id=job.id, item_id=item_id)
    except Exception as e:
        traceback.print_exc()
        w.fail_job(job, f"render failed: {type(e).__name__}: {e}", fatal=False)
        return

    # SEO + captions (platform copies)
    plat_captions = {}
    seo_pack = {}
    try:
        _geos, _lang = _account_geo(sb, account_id)
        plat_captions = _brain.captions(script, item_id=item_id, geos=_geos, language=_lang, account_id=account_id)
    except Exception:
        plat_captions = {}
    try:
        from agent import seo as _seo
        bus.agent("seo", "🔖 generating SEO / hashtags", "info", "seo_start",
                  job_id=job.id, item_id=item_id)
        seo_pack = _seo.seoize(topic, script, account_id=account_id,
                               project_id=project_id, captions=plat_captions,
                               item_id=item_id) or {}
        if seo_pack.get("hashtags"):
            # Best-effort merge into plat_captions
            for k in ("instagram", "tiktok"):
                if isinstance(plat_captions.get(k), dict):
                    plat_captions[k]["hashtags"] = seo_pack["hashtags"]
    except Exception as e:
        bus.agent("seo", f"🔖 SEO skipped (non-fatal): {str(e)[:100]}", "warn",
                  "seo_skip", job_id=job.id, item_id=item_id)

    if sb and item_id:
        board_patch_payload(sb, item_id, {
            "video_path": vid, "style": style, "script": script,
            "captions": plat_captions, "seo": seo_pack, "grade": script.get("grade"),
        })

    # Hand to post-production for repurposing + distribution
    caption_text = _compose_caption(plat_captions, seo_pack, script)
    job_of(w, "post.polish", {
        "item_id": item_id, "video_path": vid, "script": script,
        "captions": plat_captions, "seo": seo_pack, "caption_text": caption_text,
    }, parent=job, account_id=account_id, project_id=project_id,
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "video_path": vid})


# --------------------------------------------------------- helpers

def _hook_word(text: str) -> str:
    from agent.brain import _power_word
    try:
        return _power_word(text)
    except Exception:
        return "WATCH"


def _assemble_narration(script: dict) -> str:
    parts = [script.get("hook") or ""]
    for b in (script.get("beats") or []):
        t = b.get("voiceover") or b.get("text") or ""
        if t:
            parts.append(t)
    parts.append(script.get("cta") or "Follow for more.")
    return " ".join(p for p in parts if p).strip()


def _audio_duration(path: str) -> float:
    if not os.path.exists(path):
        return 15.0
    try:
        import subprocess
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            stderr=subprocess.DEVNULL, timeout=10,
        ).decode().strip()
        return float(out)
    except Exception:
        return 15.0


def _compose_caption(plat_caps: dict, seo: dict, script: dict) -> str:
    # Best single caption for publishing (Instagram preferred)
    cap = ""
    if isinstance(plat_caps.get("instagram"), dict):
        cap = plat_caps["instagram"].get("caption", "") or ""
    if not cap and isinstance(plat_caps.get("tiktok"), dict):
        cap = plat_caps["tiktok"].get("caption", "") or ""
    if not cap:
        cap = script.get("caption") or script.get("hook") or ""
    tags = seo.get("hashtags") or script.get("hashtags") or []
    if tags:
        cap = (cap + "\n\n" + " ".join(tags)).strip()
    return cap[:2000]


# ===================================================================
# v5.8 BATCH4 — CAROUSEL FORMAT (5-slide image posts, IG + TikTok photo mode)
# Cheap (~$0.10–0.25/carousel, $0 in econ mode) with real algorithmic reach.
# v1 chain: write_carousel → render_carousel → upload → status 'approved'
# (risk/monetize hooks join in a later batch; human posts from Studio).
# ===================================================================

def write_carousel(w: Worker, job: Job, ctx: AgentContext):
    from agent import llm as _llm, ledger as _ledger, brain as _brain
    from ..common import kill_switch, hard_budget_ok, brand_context_for
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    topic = job.payload.get("topic", "")
    account_id = job.account_id or job.payload.get("account_id")
    project_id = job.project_id or job.payload.get("project_id")

    if kill_switch():
        w.queue.complete(job, {"ok": False, "paused": True}); return
    if not hard_budget_ok(0.03):
        bus.agent("brain", "⛔ budget gate closed — carousel write parked", "warn",
                  "carousel_parked", job_id=job.id, item_id=item_id)
        w.queue.complete(job, {"ok": False, "budget_blocked": True}); return

    brand = {}
    try:
        brand = brand_context_for(sb, account_id) or {}
    except Exception:
        pass
    geos, lang = _account_geo(sb, account_id)
    clone_notes = (job.payload.get("source_notes") or "").strip()

    prompt = (
        "You write viral Instagram/TikTok CAROUSEL posts (image slides).\n"
        f"Topic: {topic}\n"
        f"Brand voice/context: {str(brand)[:900]}\n"
        + (f"CLONE BRIEF (recreate this ANGLE originally, never copy wording): {clone_notes[:500]}\n" if clone_notes else "")
        + (f"Audience countries: {', '.join(geos)}. Avoid region-specific slang; only universally available products.\n" if geos else "")
        + f"Language: {lang}.\n"
        "Return STRICT JSON only, no markdown:\n"
        '{"title": "...", "slides": [{"heading": "≤8 words, punchy", "body": "≤22 words"}] (exactly 5, slide 1 = scroll-stopping hook, slide 5 = CTA to follow/save), '
        '"caption": "≤300 chars with save/share CTA", "hashtags": ["#..."] (8 tags)}'
    )
    try:
        text, cost, mlabel = _llm.chat(prompt, max_tokens=900)
        _ledger.record("carousel_writer", model=mlabel, cost_usd=cost, item_id=item_id)
        import json as _json
        data = _json.loads(text[text.find("{"): text.rfind("}")+1])
        slides = data.get("slides") or []
        assert 3 <= len(slides) <= 7 and all(sl.get("heading") for sl in slides)
    except Exception as e:
        w.fail_job(job, f"carousel write failed: {str(e)[:150]}", fatal=False)
        return

    if sb and item_id:
        board_patch_payload(sb, item_id, {"carousel_script": data, "format": "carousel"})
        try:
            sb.table("board_items").update({"status": "drafted"}).eq("id", str(item_id)).execute()
        except Exception:
            pass
    bus.agent("brain", f"🖼️ carousel written: {len(slides)} slides — \"{data.get('title','')[:60]}\"",
              "success", "carousel_written", job_id=job.id, item_id=item_id)
    job_of(w, "creative.render_carousel", {
        "item_id": item_id, "carousel": data, "topic": topic,
    }, parent=job, account_id=account_id, project_id=project_id, priority=job.priority)
    w.queue.complete(job, {"ok": True, "slides": len(slides), "cost": cost})


def _slide_card(img, heading: str, body: str, idx: int, total: int):
    """Overlay heading+body on a slide (1080x1350). Dark panel keeps text readable."""
    from PIL import Image as _I, ImageDraw as _ID, ImageFont as _IF
    import textwrap as _tw
    FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    img = img.convert("RGB").resize((1080, 1920))
    img = img.crop((0, 285, 1080, 285 + 1350))  # center-crop to 4:5
    overlay = _I.new("RGBA", img.size, (0, 0, 0, 0))
    d = _ID.Draw(overlay)
    d.rounded_rectangle([40, 760, 1040, 1310], radius=36, fill=(10, 10, 14, 200))
    img = _I.alpha_composite(img.convert("RGBA"), overlay)
    d = _ID.Draw(img)
    f_h = _IF.truetype(FONT_BOLD, 66)
    f_b = _IF.truetype(FONT_REG, 44)
    f_n = _IF.truetype(FONT_BOLD, 40)
    y = 800
    for line in _tw.wrap(heading.upper(), width=24)[:3]:
        d.text((80, y), line, font=f_h, fill=(255, 255, 255, 255)); y += 78
    y += 14
    for line in _tw.wrap(body, width=42)[:4]:
        d.text((80, y), line, font=f_b, fill=(225, 225, 232, 255)); y += 56
    d.text((80, 1240), f"{idx}/{total}", font=f_n, fill=(160, 160, 180, 255))
    return img.convert("RGB")


def render_carousel(w: Worker, job: Job, ctx: AgentContext):
    from agent import visuals as _v, brain as _brain, delivery as _dl
    import os, tempfile
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    data = job.payload.get("carousel") or {}
    slides = data.get("slides") or []
    account_id = job.account_id
    if not slides:
        w.fail_job(job, "render_carousel: no slides", fatal=True); return

    style = _v.pick_style(item_id)
    tmpdir = tempfile.mkdtemp(prefix="carousel_")
    paths = []
    from PIL import Image as _I
    for i, sl in enumerate(slides, start=1):
        raw = os.path.join(tmpdir, f"raw_{i}.jpg")
        try:
            _v.beat_frame(sl.get("body",""), f"{data.get('title','')} — {sl.get('heading','')}",
                          raw, seed=i, item_id=item_id, style=style,
                          beat_idx=i-1, total_beats=len(slides))
            base = _I.open(raw)
        except Exception:
            base = _I.new("RGB", (1080, 1920), (24, 22, 34))
        out = os.path.join(tmpdir, f"slide_{i}.jpg")
        _slide_card(base, sl.get("heading",""), sl.get("body",""), i, len(slides)).save(out, quality=90)
        paths.append(out)
    bus.agent("composer", f"🖼️ {len(paths)} slides rendered", "success",
              "carousel_rendered", job_id=job.id, item_id=item_id)

    urls = _dl.upload_images(sb, paths, item_id) if sb else []
    geos, lang = _account_geo(sb, account_id)
    payload = {
        "carousel_urls": urls, "format": "carousel",
        "caption_text": (data.get("caption","") + "\n\n" + " ".join(data.get("hashtags") or [])).strip(),
        "captions": {"instagram": {"caption": data.get("caption",""), "hashtags": data.get("hashtags") or []},
                     "tiktok": {"caption": data.get("caption","")[:150], "hashtags": (data.get("hashtags") or [])[:8]},
                     "post_windows": _brain.post_windows(geos)},
    }
    if sb and item_id:
        board_patch_payload(sb, item_id, payload)
        try:
            sb.table("board_items").update({"status": "approved"}).eq("id", str(item_id)).execute()
        except Exception:
            pass
    if urls:
        bus.agent("composer", f"⬆️ carousel uploaded ({len(urls)} images) — ready in Studio",
                  "success", "carousel_ready", job_id=job.id, item_id=item_id)
    else:
        bus.agent("composer", "⚠️ carousel upload failed — images only on worker disk",
                  "warn", "carousel_upload_missing", job_id=job.id, item_id=item_id)
    w.queue.complete(job, {"ok": True, "images": len(paths), "uploaded": len(urls)})
