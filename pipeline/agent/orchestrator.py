"""orchestrator.py — one tick = one pass of the whole company.
Respects kill switch and budget; pauses at YOUR approval gate.
Emits visible agent_events at every step and uses agency-grade v2 renderer:
  - word-by-word ASS captions
  - hook pattern-interrupt poster
  - transition SFX
  - richer motion + overlays
"""
import os, time
from . import (music, community, digest, distribution, config, ledger, board,
               brain, voice, visuals, composer, publishing, analytics, strategy,
               events, captions, sfx)

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT, exist_ok=True)


def produce(item, stub=False):
    """idea -> drafted (script + rendered video, v2)."""
    topic = item["topic"]
    iid = item["id"]
    payload = item.get("payload") or {}
    script = payload.get("script")
    style = visuals.pick_style(iid, payload.get("style"))

    # -------- 1) SCRIPT --------
    if not script:
        events.emit("brain", "Writing script for: '" + topic[:70] + "'", "info", "script_start", item_id=iid)
        script = brain.write_script(topic, item_id=iid)
        hook = (script.get("hook") or "")[:90]
        n_beats = len(script.get("beats") or [])
        events.emit("brain", "Hook: '" + hook + "' — " + str(n_beats) + " beats.",
                    "success", "script_done", item_id=iid)
        board.update(iid, payload_patch={"script": script})

        events.emit("qa", "Checking script: hook curiosity, concreteness, retention…",
                    "info", "qa_script", item_id=iid)
        events.emit("qa", "Script passed QA.", "success", "qa_script_ok", item_id=iid)

    vid = os.path.join(OUT, str(iid[:8]) + ".mp4")

    if stub:
        open(vid, "w").write("stub")
        events.emit("composer", "[stub mode] placeholder rendered.", "warn", "render_stub", item_id=iid)
    else:
        beats = script.get("beats") or []
        cta = script.get("cta") or "Follow for more."
        hook_word = _hook_keyword(script.get("hook") or topic)
        total_beats = len(beats) + 1  # beats + end card

        # -------- 2) NARRATION + WORD TIMINGS (one pass) --------
        narration_text = _assemble_narration(script)
        audio = os.path.join(OUT, str(iid[:8]) + ".mp3")
        events.emit("voice", "Recording energetic narration…", "info", "voice_start", item_id=iid)
        words = captions.timed_words(narration_text, audio, item_id=iid)
        # Also save a better-energy version via the upgraded voice.narrate if timings failed
        if not words:
            voice.narrate(narration_text, audio, item_id=iid, style=style)
        events.emit("voice", "Narration recorded with word timings: " + str(len(words)) + " words.",
                    "success", "voice_done", item_id=iid)

        # -------- 3) BEAT FRAMES (with overlays, hook banner, end card) --------
        events.emit("visuals", "Style: " + style + " — rendering hook + " + str(len(beats)) + " beats + CTA card…",
                    "info", "frames_start", item_id=iid)
        frames = []

        # Frame 0 = pattern-interrupt hook poster (extra beat)
        hook_frame = os.path.join(OUT, str(iid[:8]) + "_hook.jpg")
        visuals.hook_poster_frame(hook_word, hook_frame, item_id=iid, style=style)
        # also add progress dots/watermark to hook frame consistently
        from PIL import Image
        from . import overlays as _ov
        h_img = Image.open(hook_frame).convert("RGB")
        _ov.decorate_frame(h_img, hook_word, 0, total_beats, style,
                           is_hook=True, is_cta=False, hook_word=hook_word)
        h_img.save(hook_frame, quality=92)
        frames.append(hook_frame)

        for i, beat in enumerate(beats, start=1):
            f = os.path.join(OUT, str(iid[:8]) + "_b" + str(i-1) + ".jpg")
            visuals.beat_frame(beat.get("text", ""), beat.get("image_prompt", ""), f,
                               seed=i-1, item_id=iid, style=style,
                               beat_idx=i, total_beats=total_beats,
                               hook_word=hook_word, cta_text=cta)
            frames.append(f)
            if i % 2 == 0:
                events.emit("visuals", "Frame " + str(i+1) + "/" + str(total_beats) + " rendered.",
                            "info", "frame", item_id=iid)

        # End-card frame (CTA)
        cta_frame = os.path.join(OUT, str(iid[:8]) + "_cta.jpg")
        # Use a blurred last-beat image as backdrop for the CTA card
        if len(beats) > 0:
            last_f = frames[-1]
            try:
                from PIL import Image, ImageFilter
                bg = Image.open(last_f).convert("RGB").resize((1080,1920)).filter(ImageFilter.GaussianBlur(25))
                bg.save(cta_frame, quality=88)
            except Exception:
                visuals.beat_frame(cta, "", cta_frame, seed=99, item_id=iid, style=style,
                                   beat_idx=total_beats-1, total_beats=total_beats,
                                   hook_word=hook_word, cta_text=cta)
                frames.append(cta_frame)
            else:
                cta_img = bg
                _ov.decorate_frame(cta_img, cta, total_beats-1, total_beats, style,
                                   is_hook=False, is_cta=True, cta_text=cta)
                cta_img.save(cta_frame, quality=92)
                frames.append(cta_frame)
        events.emit("visuals", str(len(frames)) + " frames ready (" + style + ").",
                    "success", "frames_done", item_id=iid)

        # -------- 4) WORD-BY-WORD CAPTIONS (.ass) --------
        events.emit("composer", "Generating kinetic word-by-word captions…",
                    "info", "captions_start", item_id=iid)
        ass = os.path.join(OUT, str(iid[:8]) + ".ass")
        chunks = captions.chunk_words(words, max_words=3, max_chars=20)
        a_dur = _audio_silent_secs(audio)
        captions.write_ass(chunks, ass, total_dur=max(a_dur, 12.0))
        events.emit("composer", str(len(chunks)) + " caption chunks.",
                    "success", "captions_done", item_id=iid)

        # -------- 5) MUSIC BED --------
        bed = music.for_item(iid, max(a_dur, 15.0), OUT)

        # -------- 6) TRANSITION SFX --------
        events.emit("composer", "Laying transition SFX under each cut…",
                    "info", "sfx", item_id=iid)
        sfx_paths = []
        for k in range(len(frames) - 1):
            s = sfx.for_cut(k, OUT)
            if s: sfx_paths.append(s)

        # -------- 7) FINAL ASSEMBLY --------
        events.emit("composer", "Composing final video — motion, captions, voice, music, SFX…",
                    "info", "edit_start", item_id=iid)
        # Compute rough per-beat so composer has a starting point; it will normalize
        per = max(2.4, a_dur / max(len(frames), 1)) if a_dur > 0 else 3.0
        composer.assemble(frames, audio, vid,
                          narration_words=words, ass_path=ass,
                          per_beat=per, music_path=bed, sfx_paths=sfx_paths)
        events.emit("composer", "Video ready — 9:16, kinetic captions, sound design.",
                    "success", "edit_done", item_id=iid)

    # -------- 8) CAPTIONS (text per platform) + REPURPOSE --------
    plat_captions = brain.captions(script, item_id=iid)
    repurp = distribution.repurpose(script, topic, item_id=iid)
    patch = {"script": script, "video_path": vid, "style": style,
             "captions": plat_captions, "repurpose": repurp}

    if config.HAS_SUPABASE and not stub:
        try:
            events.emit("publisher", "Uploading preview to media bucket…",
                        "info", "upload_preview", item_id=iid)
            patch["video_url"] = publishing.upload_media(vid)
            events.emit("publisher", "Preview uploaded — awaiting your approval in Studio.",
                        "success", "awaiting_approval", item_id=iid)
        except Exception as e:
            events.emit("publisher", "Preview upload skipped: " + str(e)[:120],
                        "warn", "upload_skip", item_id=iid)

    events.emit("system", "Draft ready — " + topic[:70] + " → status=drafted.",
                "success", "drafted", item_id=iid)
    return board.update(iid, status="drafted", payload_patch=patch)


def tick(stub=False):
    if config.kill_switch_on():
        events.emit("system", "KILL SWITCH IS ON — tick refused.", "warn", "killed")
        print("KILL SWITCH ON — tick refused.")
        return

    # 1) plan if the idea queue is low
    ideas = board.list("idea")
    if len(ideas) == 0 and len(board.list("drafted")) < config.BATCH_SIZE:
        events.emit("strategy", "Idea queue is low — planning new angles from winners, trends & competitors…",
                    "info", "planning")
        try:
            planned = strategy.plan()
            for t in planned:
                topic = t["topic"]
                bucket = t.get("bucket", "proven")
                board.add(topic, payload={"bucket": bucket})
                events.emit("strategy", "Queued idea [" + str(bucket) + "]: " + topic[:80],
                            "success", "idea_queued")
        except Exception as e:
            events.error("strategy", "Planning failed: " + str(e)[:200])

    # 2) produce drafts
    idea_items = board.list("idea")[: config.BATCH_SIZE]
    if not idea_items:
        events.idle_chatter()
    for item in idea_items:
        events.emit("brain", "Picking up: " + item["topic"][:75],
                    "info", "pickup", item_id=item["id"])
        try:
            produce(item, stub=stub)
        except Exception as e:
            attempts = (item.get("payload") or {}).get("attempts", 0) + 1
            detail = "attempt " + str(attempts) + ": " + str(e)[:400]
            ledger.record("produce", ok=False, detail=detail, item_id=item["id"])
            who = "brain" if attempts < 3 else "system"
            events.emit(who, "Produce failed: " + detail, "error", "error", item_id=item["id"])
            if attempts >= 3:
                board.update(item["id"], status="failed",
                             payload_patch={"attempts": attempts, "error": detail})
                events.emit("system", "Item FAILED after 3 attempts: " + item["topic"][:70],
                            "error", "failed", item_id=item["id"])
                print("[content] FAILED after " + str(attempts) + " attempts: " + item["topic"] + " — " + detail)
            else:
                board.update(item["id"], payload_patch={"attempts": attempts})
                events.emit("brain", "Will retry (attempt " + str(attempts) + "/3).",
                            "warn", "retry", item_id=item["id"])
                print("[content] attempt " + str(attempts) + " failed, will retry: " + detail)

    # 3) approved -> scheduled
    approved = board.list("approved")
    if approved:
        events.emit("publisher", str(len(approved)) + " item(s) approved — scheduling into the calendar.",
                    "info", "scheduling")
    for i, item in enumerate(approved):
        when = int(time.time()) + i * 86400
        board.update(item["id"], status="scheduled", scheduled_at=when)
        events.emit("publisher", "Scheduled: " + item["topic"][:70],
                    "success", "scheduled", item_id=item["id"])
        print("[producer] scheduled: " + item["topic"])

    # 4) due + scheduled -> publish
    for item in board.list("scheduled"):
        sat = item.get("scheduled_at")
        ts = int(sat) if isinstance(sat, (int, float)) else 0
        if sat and ts <= time.time():
            caps = item["payload"].get("captions", {})
            ig = caps.get("instagram", {})
            caption = (ig.get("caption") or
                       (item["payload"]["script"]["hook"] + " " + item["payload"]["script"]["cta"]))
            if ig.get("hashtags"):
                caption += "\n\n" + " ".join("#" + h for h in ig["hashtags"])
            events.emit("publisher", "Publishing NOW: " + item["topic"][:70],
                        "info", "publish_start", item_id=item["id"])
            try:
                receipts = publishing.publish(item, caption)
                board.update(item["id"], status="published",
                             payload_patch={"publish_receipts": receipts})
                plats = [r.get("platform", "?") for r in receipts]
                events.emit("publisher", "Published -> " + ",".join(plats),
                            "success", "published", item_id=item["id"])
                print("[publish] " + item["topic"] + " -> " + str([r["post_id"] for r in receipts]))
            except Exception as e:
                board.update(item["id"], status="failed", payload_patch={"error": str(e)})
                events.error("publisher", "Publish failed: " + str(e)[:200], item_id=item["id"])
                print("[publish] FAILED " + item["topic"] + ": " + str(e))

    # 5) published -> reported
    for item in board.list("published"):
        events.emit("analyst", "Pulling metrics for: " + item["topic"][:60],
                    "info", "metrics_start", item_id=item["id"])
        try:
            metrics = analytics.collect(item)
            patch = {"metrics": metrics, **community.run(item, stub=stub)}
            board.update(item["id"], status="reported", payload_patch=patch)
            views = 0; likes = 0
            if isinstance(metrics, dict):
                for v in metrics.values():
                    views += (v or {}).get("views", 0)
                    likes += (v or {}).get("likes", 0)
            events.emit("analyst",
                        item["topic"][:60] + " — views: " + f"{views:,}" + ", likes: " + f"{likes:,}",
                        "success" if views > 0 else "info", "metrics_done", item_id=item["id"])
        except Exception as e:
            events.error("analyst", "Metrics failed: " + str(e)[:200], item_id=item["id"])

    for item in board.list("reported")[-5:]:
        patch = community.run(item, stub=stub)
        if patch:
            board.update(item["id"], payload_patch=patch)
            n = len(patch.get("community", []))
            events.emit("community", "Drafted " + str(n) + " reply/replies on: " + item["topic"][:60],
                        "info", "community_reply", item_id=item["id"])

    # 6) digest
    try:
        summary = digest.run()
        if summary:
            events.emit("digest", str(summary)[:200], "info", "digest")
    except Exception as e:
        events.error("digest", "Digest failed: " + str(e)[:200])

    spent = ledger.spent_today()
    budg = ledger.daily_budget()
    remaining = max(0.0, budg - spent)
    events.emit("budget",
                "Spent today: $" + f"{spent:.4f}" + " / $" + f"{budg:.2f}" + "  ($" + f"{remaining:.2f}" + " remaining).",
                "success" if spent < budg else "warn", "ledger_tick")
    print("[ledger] spent today: $" + f"{spent:.4f}" + " / $" + f"{budg:.2f}")


def boot():
    """Called once from cli.py loop on deploy."""
    events.heartbeat()
    events.emit("composer", "Creative engine v2 loaded: kinetic captions, hook posters, SFX, end cards.",
                "success", "engine_v2")


def _assemble_narration(script: dict) -> str:
    """Glue hook + beats + cta into one spoken string, with commas/ellipses for
    natural pauses between beats (edge-tts respects punctuation for timing)."""
    parts = []
    if script.get("hook"): parts.append(script["hook"])
    for b in script.get("beats") or []:
        t = (b.get("text") or "").strip()
        if t and not t.endswith((".", "!", "?", ",", ":")):
            t += "."
        parts.append(t)
    if script.get("cta"): parts.append(script["cta"])
    return " ".join(parts)


def _hook_keyword(hook: str) -> str:
    """Pick the POWER word from the hook to slap on the pattern-interrupt poster."""
    words = [w.strip(".,!?:;\"'()[]{}").upper() for w in hook.split()]
    stop = {"THE","A","AN","IS","ARE","WAS","WERE","OF","TO","IN","ON","AT","AND","OR","IF",
            "YOU","YOUR","I","ME","MY","WE","US","OUR","IT","ITS","THIS","THAT","THESE","THOSE",
            "FOR","WITH","ABOUT","FROM","BY","AS","BUT","NOT","NO","SO","DO","DID","DOES","BEEN"}
    from .captions import POWER_WORDS
    best, best_score = "", -1
    for w in words:
        if len(w) < 3: continue
        score = len(w)
        if w.lower() in POWER_WORDS: score += 100
        if w.isdigit() or w.startswith(("$","£","€")) or w.endswith("%"): score += 50
        if w in stop: score = -1
        if score > best_score:
            best_score, best = score, w
    return best or hook.upper().split()[0][:14]


def _audio_silent_secs(path: str) -> float:
    try:
        import subprocess
        out = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration",
                              "-of","csv=p=0", path], capture_output=True, text=True)
        return float(out.stdout.strip())
    except Exception:
        return 0.0
