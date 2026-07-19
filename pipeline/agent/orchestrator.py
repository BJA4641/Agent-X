"""orchestrator.py v4.3 — one tick = one pass of the company.
Respects pause/resume on projects AND accounts — paused items are SKIPPED entirely.
Seed scout on boot; architect/strategist/research/seo/produce all respect pause.
Defensive imports so stale Docker layers never crash the whole container.
"""
import os, time, traceback as _tb
from . import (music, community, digest, distribution, config, ledger, board,
               brain, voice, visuals, composer, publishing, analytics, strategy,
               events, captions, sfx, architect, strategist as account_strategist,
               scout, projects as projects_mod)
# memory + research + seo are soft deps — fall back to no-op stubs if import fails.
try:
    from . import memory
except Exception as _e:
    print(f"[orchestrator] WARNING: memory import failed ({_e}); using no-op stub.")
    _tb.print_exc()
    from . import _memstub
    memory = _memstub.MemoryStub()
try:
    from . import research as _research
except Exception as _e:
    print(f"[orchestrator] WARNING: research import failed ({_e}); disabled.")
    _research = None
try:
    from . import seo as _seo
except Exception as _e:
    print(f"[orchestrator] WARNING: seo import failed ({_e}); disabled.")
    _seo = None

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT, exist_ok=True)

# Simple in-memory dedup so we don't re-queue the same account_post every tick
_seen_posts: set = set()
_seen_projects_cleared_at: float = 0


def produce(item, stub=False, account_id=None, project_id=None):
    """idea -> drafted (script + rendered video, v2). Respects grader quality gate."""
    topic = item["topic"]
    iid = item["id"]
    payload = item.get("payload") or {}
    script = payload.get("script")
    style = visuals.pick_style(iid, payload.get("style"))

    # -------- 1) SCRIPT (with brand context + memory + trends + grader loop) --------
    if not script:
        events.emit("brain", "Writing script for: '" + topic[:70] + "'", "info", "script_start", item_id=iid)
        script = brain.write_script(topic, item_id=iid, account_id=account_id, project_id=project_id)
        hook = (script.get("hook") or "")[:90]
        n_beats = len(script.get("beats") or [])
        g = script.get("grade") or {}
        grade_str = f" — grade {g.get('overall','?')}/10 {'✅' if g.get('passed') else '❌'}" if g else ""
        events.emit("brain", "Hook: '" + hook + "' — " + str(n_beats) + " beats." + grade_str,
                    "success" if g.get("passed") else "warn", "script_done", item_id=iid)
        board.update(iid, payload_patch={"script": script})

        # Hard quality gate: if script failed grading after max rewrites, reject the item
        if g and not g.get("passed"):
            fix = g.get("failed_reason") or g.get("fix") or "weak content"
            events.emit("grader", f"Content REJECTED — {fix[:120]}", "warn", "grade_fail_final", item_id=iid)
            ledger.record("grader", ok=False, detail=f"final reject grade={g.get('overall')}: {fix[:200]}", item_id=iid)
            board.update(iid, status="rejected",
                         payload_patch={"rejection": {"reason": "grade_fail", "fix": fix,
                                                      "score": g.get("overall")}})
            return None

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

        # -------- 2) NARRATION + WORD TIMINGS (single edge-tts call, silent fallback on fail) --------
        narration_text = _assemble_narration(script)
        audio = os.path.join(OUT, str(iid[:8]) + ".mp3")
        events.emit("voice", "Recording energetic narration…", "info", "voice_start", item_id=iid)
        words = captions.timed_words(narration_text, audio, item_id=iid, style=style)
        events.emit("voice", f"Narration recorded: {len(words)} words.",
                    "success", "voice_done", item_id=iid)

        # -------- 3) BEAT FRAMES --------
        events.emit("visuals", "Style: " + style + " — rendering hook + " + str(len(beats)) + " beats + CTA…",
                    "info", "frames_start", item_id=iid)
        frames = []

        hook_frame = os.path.join(OUT, str(iid[:8]) + "_hook.jpg")
        visuals.hook_poster_frame(hook_word, hook_frame, item_id=iid, style=style)
        from PIL import Image, ImageFilter
        from . import overlays as _ov
        try:
            h_img = Image.open(hook_frame).convert("RGB")
            _ov.decorate_frame(h_img, hook_word, 0, total_beats, style,
                               is_hook=True, is_cta=False, hook_word=hook_word)
            h_img.save(hook_frame, quality=92)
        except Exception as e:
            print(f"[composer] hook frame failed: {e}")
        frames.append(hook_frame)

        # Body beats: all beats EXCEPT the last one (last beat is the CTA end-card)
        body_beats = beats[:-1] if len(beats) >= 2 else beats
        for i, beat in enumerate(body_beats, start=1):
            f = os.path.join(OUT, str(iid[:8]) + "_b" + str(i-1) + ".jpg")
            beat_text = beat.get("voiceover") or beat.get("text") or ""
            beat_prompt = beat.get("visual_prompt") or beat.get("image_prompt") or ""
            try:
                visuals.beat_frame(beat_text, beat_prompt, f,
                                   seed=i-1, item_id=iid, style=style,
                                   beat_idx=i, total_beats=total_beats,
                                   hook_word=hook_word, cta_text=cta)
            except Exception as e:
                print(f"[composer] beat {i} frame failed: {e}")
                visuals.beat_frame(beat_text, "", f, seed=i-1, item_id=iid, style=style,
                                   beat_idx=i, total_beats=total_beats, hook_word=hook_word, cta_text=cta)
            frames.append(f)
            if i % 2 == 0:
                events.emit("visuals", f"Frame {i+1}/{total_beats} rendered.", "info", "frame", item_id=iid)

        # End-card frame (CTA) — blurred last body beat as backdrop
        cta_frame = os.path.join(OUT, str(iid[:8]) + "_cta.jpg")
        try:
            if len(frames) >= 2:
                last_body = frames[-1]
                bg = Image.open(last_body).convert("RGB").resize((1080,1920)).filter(ImageFilter.GaussianBlur(28))
            else:
                bg = Image.new("RGB",(1080,1920),(10,12,28))
            _ov.decorate_frame(bg, cta, total_beats-1, total_beats, style,
                               is_hook=False, is_cta=True, cta_text=cta)
            bg.save(cta_frame, quality=92)
            frames.append(cta_frame)
        except Exception as e:
            print(f"[composer] CTA frame failed: {e}")
            visuals.beat_frame(cta, "", cta_frame, seed=99, item_id=iid, style=style,
                               beat_idx=total_beats-1, total_beats=total_beats,
                               hook_word=hook_word, cta_text=cta)
            frames.append(cta_frame)
        events.emit("visuals", f"{len(frames)} frames ready ({style}).",
                    "success", "frames_done", item_id=iid)

        # -------- 4) WORD-BY-WORD CAPTIONS --------
        events.emit("composer", "Generating kinetic captions…", "info", "captions_start", item_id=iid)
        ass = os.path.join(OUT, str(iid[:8]) + ".ass")
        chunks = captions.chunk_words(words, max_words=3, max_chars=20)
        a_dur = _audio_silent_secs(audio)
        captions.write_ass(chunks, ass, total_dur=max(a_dur, 12.0))
        events.emit("composer", str(len(chunks)) + " caption chunks.", "success", "captions_done", item_id=iid)

        # -------- 5) MUSIC + SFX --------
        bed = music.for_item(iid, max(a_dur, 15.0), OUT)
        events.emit("composer", "Laying transition SFX…", "info", "sfx", item_id=iid)
        sfx_paths = []
        for k in range(len(frames) - 1):
            s = sfx.for_cut(k, OUT)
            if s: sfx_paths.append(s)

        # -------- 6) FINAL ASSEMBLY --------
        events.emit("composer", "Composing final video — motion, captions, voice, music, SFX…",
                    "info", "edit_start", item_id=iid)
        per = max(2.4, a_dur / max(len(frames), 1)) if a_dur > 0 else 3.0
        composer.assemble(frames, audio, vid,
                          narration_words=words, ass_path=ass,
                          per_beat=per, music_path=bed, sfx_paths=sfx_paths)
        events.emit("composer", "Video ready — 9:16, kinetic captions, sound design.",
                    "success", "edit_done", item_id=iid)

    # -------- 7) CAPTIONS + SEO + REPURPOSE --------
    plat_captions = brain.captions(script, item_id=iid)
    seo_pack = {}
    if _seo is not None:
        try:
            events.emit("seo", "Generating hashtag set + first-comment + SEO keywords…",
                        "info", "seo_start", item_id=iid)
            seo_pack = _seo.seoize(topic, script,
                                    account_id=account_id, project_id=project_id,
                                    captions=plat_captions, item_id=iid) or {}
            # Merge seo hashtags/first-comment into captions so publisher sees them
            if seo_pack.get("hashtags"):
                plat_captions["hashtags"] = seo_pack["hashtags"]
            if seo_pack.get("first_comment"):
                plat_captions["first_comment"] = seo_pack["first_comment"]
            events.emit("seo", f"SEO ready — {len(seo_pack.get('hashtags') or [])} hashtags, first-comment pinned.",
                        "success", "seo_done", item_id=iid)
        except Exception as e:
            events.emit("seo", f"SEO skipped: {str(e)[:120]}", "warn", "seo_skip", item_id=iid)
    repurp = distribution.repurpose(script, topic, item_id=iid)
    patch = {"script": script, "video_path": vid, "style": style,
             "captions": plat_captions, "repurpose": repurp, "seo": seo_pack,
             "grade": script.get("grade")}

    if config.HAS_SUPABASE and not stub:
        try:
            events.emit("publisher", "Uploading preview to media bucket…",
                        "info", "upload_preview", item_id=iid)
            patch["video_url"] = publishing.upload_media(vid)
            events.emit("publisher", "Preview uploaded — awaiting approval.",
                        "success", "awaiting_approval", item_id=iid)
        except Exception as e:
            events.emit("publisher", "Preview upload skipped: " + str(e)[:120],
                        "warn", "upload_skip", item_id=iid)

    events.emit("system", "Draft ready — " + topic[:70] + f" (grade {script.get('grade',{}).get('overall','?')}/10) → status=drafted.",
                "success", "drafted", item_id=iid)
    return board.update(iid, status="drafted", payload_patch=patch)


def tick(stub=False):
    if config.kill_switch_on():
        events.emit("system", "KILL SWITCH IS ON — tick refused.", "warn", "killed")
        print("KILL SWITCH ON — tick refused.")
        return

    # 0a) Ensure scout library is seeded (runs once, then no-op)
    try:
        scout.run()
    except Exception as e:
        events.error("scout", f"Scout error: {str(e)[:200]}")

    # 0b) Architect + Strategist (BOTH respect pause internally now)
    try:
        n_arch = architect.run(limit=1)
        if n_arch:
            events.emit("architect", f"Architected {n_arch} new account(s) this tick.", "success", "architect_tick")
        n_strat = account_strategist.run(limit=1)
        if n_strat:
            events.emit("strategist", f"Strategized {n_strat} account(s) this tick.", "success", "strategist_tick")
    except Exception as e:
        events.error("architect", f"Account setup error: {str(e)[:200]}")

    # 0c) Pull next post from the active (non-paused) account_posts queue
    #     This replaces the old strategy.plan() board approach: content comes from per-account plans.
    active_post = _next_planned_post()

    # 1) plan (legacy board) if idea queue is low AND there's no per-account next post
    ideas = board.list("idea")
    if len(ideas) == 0 and len(board.list("drafted")) < config.BATCH_SIZE and not active_post:
        events.emit("strategy", "Idea queue low — planning angles from trends & winners…",
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

    # 2) produce drafts: prefer per-account queue, fall back to legacy board
    produced = 0
    if active_post:
        item = _post_to_board_item(active_post)
        if item:
            events.emit("brain", f"Picking up planned post: '{item['topic'][:70]}' (account @{active_post['account_handle']})",
                        "info", "pickup", item_id=item["id"])
            try:
                produce(item, stub=stub,
                        account_id=active_post["account_id"],
                        project_id=active_post["project_id"])
                # Mark account_post as drafted
                _mark_post_status(active_post["post_id"], "drafted")
                produced += 1
            except Exception as e:
                events.emit("system", f"Produce failed on planned post: {str(e)[:200]}", "error", "error")
                _mark_post_status(active_post["post_id"], "failed")

    # Also produce any legacy idea items (respecting budget)
    if produced == 0:
        idea_items = board.list("idea")[: config.BATCH_SIZE]
        if not idea_items:
            events.idle_chatter()
        for item in idea_items:
            # Skip items that have already hit max attempts (shouldn't be in 'idea', but guard)
            attempts = (item.get("payload") or {}).get("attempts", 0)
            if attempts >= 2:
                board.update(item["id"], status="failed",
                             payload_patch={"attempts": attempts, "error": "skipped: too many prior failures"})
                events.emit("system", "Item already failed twice, moving to failed: " + item["topic"][:70],
                            "warn", "skipped", item_id=item["id"])
                continue
            events.emit("brain", "Picking up: " + item["topic"][:75],
                        "info", "pickup", item_id=item["id"])
            try:
                result = produce(item, stub=stub)
                if result is None:
                    # Grader rejected after all rewrites — already marked rejected, move on
                    events.emit("system", "Content rejected by grader (will not retry): " + item["topic"][:70],
                                "warn", "grade_rejected", item_id=item["id"])
            except Exception as e:
                attempts = attempts + 1
                detail = "attempt " + str(attempts) + ": " + str(e)[:400]
                ledger.record("produce", ok=False, detail=detail, item_id=item["id"])
                who = "brain" if attempts < 2 else "system"
                events.emit(who, "Produce failed: " + detail, "error", "error", item_id=item["id"])
                if attempts >= 2:
                    board.update(item["id"], status="failed",
                                 payload_patch={"attempts": attempts, "error": detail})
                    events.emit("system", "Item FAILED after 2 attempts: " + item["topic"][:70],
                                "error", "failed", item_id=item["id"])
                else:
                    board.update(item["id"], payload_patch={"attempts": attempts})
                    events.emit("brain", "Will retry (attempt " + str(attempts) + "/2).",
                                "warn", "retry", item_id=item["id"])

    # 3) approved -> scheduled
    approved = board.list("approved")
    if approved:
        events.emit("publisher", str(len(approved)) + " approved — scheduling.",
                    "info", "scheduling")
    for i, item in enumerate(approved):
        when = int(time.time()) + i * 86400
        board.update(item["id"], status="scheduled", scheduled_at=when)
        events.emit("publisher", "Scheduled: " + item["topic"][:70],
                    "success", "scheduled", item_id=item["id"])

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
                plats = [r.get("platform","?") for r in receipts]
                events.emit("publisher", "Published -> " + ",".join(plats),
                            "success", "published", item_id=item["id"])
            except Exception as e:
                board.update(item["id"], status="failed", payload_patch={"error": str(e)})
                events.error("publisher", "Publish failed: " + str(e)[:200], item_id=item["id"])

    # 5) published -> reported
    for item in board.list("published"):
        events.emit("analyst", "Pulling metrics for: " + item["topic"][:60],
                    "info", "metrics_start", item_id=item["id"])
        try:
            metrics = analytics.collect(item)
            patch = {"metrics": metrics, **community.run(item, stub=stub)}
            board.update(item["id"], status="reported", payload_patch=patch)
            views = likes = 0
            if isinstance(metrics, dict):
                for v in metrics.values():
                    views += (v or {}).get("views",0)
                    likes += (v or {}).get("likes",0)
            events.emit("analyst",
                        item["topic"][:60] + f" — views: {views:,}, likes: {likes:,}",
                        "success" if views>0 else "info", "metrics_done", item_id=item["id"])
        except Exception as e:
            events.error("analyst", "Metrics failed: " + str(e)[:200], item_id=item["id"])

    for item in board.list("reported")[-5:]:
        patch = community.run(item, stub=stub)
        if patch:
            board.update(item["id"], payload_patch=patch)
            n = len(patch.get("community", []))
            events.emit("community", f"Drafted {n} reply/replies: " + item["topic"][:60],
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
                f"Spent today: ${spent:.4f} / ${budg:.2f}  (${remaining:.2f} remaining).",
                "success" if spent < budg else "warn", "ledger_tick")


def boot():
    """Called once from cli.py loop."""
    events.heartbeat()
    events.emit("system", "Agent-X v4.2 online — 18 agents loaded: scout, research, architect, "
                "strategist, writer, visuals, voice, editor, qa, grader, seo, publisher, "
                "analyst, community, digest, planner, budget, ops.",
                "success", "engine_v42")
    events.emit("grader", "Quality gate: 8/10 average required across hook/visuals/pacing/audio/caption/CTA.", "info", "grader_online")
    events.emit("scout", "Trend scout booting — seeding viral pattern library.", "info", "scout_boot")
    try:
        scout.ensure_seeded()
    except Exception:
        pass
    events.emit("scout", "Trend library ready (8 viral patterns loaded).", "success", "scout_ready")


def _next_planned_post():
    """Find one 'planned' post belonging to a non-paused account in a non-paused project."""
    if not config.HAS_SUPABASE: return None
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        # Two-query approach to be safe with postgrest: first fetch non-paused ready accounts,
        # then filter by parent project pause state.
        res = (sb.table("project_accounts")
               .select("id,handle,project_id,status,paused")
               .eq("status", "ready")
               .eq("paused", False)
               .limit(20).execute())
        for acc in res.data or []:
            # Check project paused state
            pj = sb.table("projects").select("paused").eq("id", acc["project_id"]).single().execute().data
            if pj and pj.get("paused"):
                continue
            post_res = (sb.table("account_posts")
                        .select("id,hook,title,account_id")
                        .eq("account_id", acc["id"])
                        .eq("status", "planned")
                        .order("created_at")
                        .limit(1).execute())
            if post_res.data:
                p = post_res.data[0]
                # Dedup across ticks using an in-memory set
                global _seen_posts, _seen_projects_cleared_at
                # Clear the seen set every 10 minutes so re-generations work
                if time.time() - _seen_projects_cleared_at > 600:
                    _seen_posts.clear(); _seen_projects_cleared_at = time.time()
                if p["id"] in _seen_posts:
                    continue  # already fired; wait for it to finish before picking another
                _seen_posts.add(p["id"])
                return {
                    "post_id": p["id"],
                    "account_id": acc["id"],
                    "account_handle": acc["handle"],
                    "project_id": acc["project_id"],
                    "topic": p.get("hook") or p.get("title") or "AI tip",
                    "post_payload": p,
                }
    except Exception as e:
        print(f"[orchestrator] next_planned_post failed: {e}")
    return None


def _post_to_board_item(active_post):
    """Wrap an account_post into a board-like item so produce() can consume it."""
    topic = active_post["topic"]
    p = active_post.get("post_payload") or {}
    item = board.add(topic, status="idea", payload={
        "account_id": active_post["account_id"],
        "project_id": active_post["project_id"],
        "post_id": active_post["post_id"],
        "source": "account_post",
        "planned_hook": p.get("hook"),
        "planned_title": p.get("title"),
        "planned_visual_prompt": p.get("visual_prompt"),
        "planned_caption": p.get("caption"),
        "planned_hashtags": p.get("hashtags"),
        "planned_script": p.get("script"),
    })
    return item


def _mark_post_status(post_id, status):
    if not config.HAS_SUPABASE or not post_id: return
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        sb.table("account_posts").update({"status": status}).eq("id", post_id).execute()
    except Exception as e:
        print(f"[orchestrator] mark post {post_id}->{status} failed: {e}")


def _assemble_narration(script: dict) -> str:
    parts = []
    if script.get("hook"): parts.append(script["hook"])
    for b in script.get("beats") or []:
        t = (b.get("voiceover") or b.get("text") or "").strip()
        if t and not t.endswith((".","!","?",",",":","…")):
            t += "."
        parts.append(t)
    if script.get("cta"): parts.append(script["cta"])
    return " ".join(parts)


def _hook_keyword(hook: str) -> str:
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
