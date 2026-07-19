"""departments/creative.py — D (Creative).

write_script: uses brain.write_script (v4.3, with grader loop INLINE the first
              draft), then hands the result to CQO for centralized grading.
render:      runs orchestrator.produce's render pipeline (voice + visuals +
              composer + captions) on a passed script, outputting a final mp4
              at output/<id>.mp4. Sends to post-production for polish.
"""
from __future__ import annotations
import os, time, traceback
from agentcore import Worker, Job, AgentContext, Priority, FatalError
from ..common import (board_patch_payload, board_get, OUTPUT_DIR,
                      brand_context_for, job_of, load_account)


def register(w: Worker):
    w.register("creative.write_script", write_script)
    w.register("creative.render",       render)


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

    # v5.3 BUG FIX: preflight check BEFORE spending on script LLM call
    from ..common import kill_switch, hard_budget_ok, remaining_budget
    if kill_switch():
        bus.agent("brain", "⏸ kill switch on — write held", "warn", "script_held",
                  job_id=job.id, item_id=item_id)
        w.queue.complete(job, {"ok": False, "paused": True})
        return
    if not hard_budget_ok(next_cost_usd=0.05):
        bus.agent("cfo", f"⏸ budget too low for script (${remaining_budget():.3f} left) — delaying",
                  "warn", "script_budget", job_id=job.id)
        # Reschedule in 1 hour instead of failing
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

    # v5.3 BUDGET CHECK before render (render itself is cheap — uses Gemini for
    # visuals which is free-tier, but LLM steps + any paid voice cost money)
    from ..common import kill_switch, hard_budget_ok, remaining_budget
    if kill_switch():
        bus.agent("composer", "⏸ kill switch on — render held", "warn", "render_held",
                  job_id=job.id, item_id=item_id)
        w.queue.complete(job, {"ok": False, "paused": True})
        return
    if not hard_budget_ok(next_cost_usd=0.01):
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

        # 1) narration
        narration = _assemble_narration(script)
        bus.agent("voice", "🎙️ recording narration…", "info", "voice_start",
                  job_id=job.id, item_id=item_id)
        words = _capmod.timed_words(narration, audio, item_id=item_id, style=style)
        bus.agent("voice", f"🎙️ narration recorded — {len(words)} words", "success",
                  "voice_done", job_id=job.id, item_id=item_id)

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
        plat_captions = _brain.captions(script, item_id=item_id)
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
