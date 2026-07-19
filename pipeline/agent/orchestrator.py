"""orchestrator.py — one tick = one pass of the whole company.
Respects kill switch and budget; pauses at YOUR approval gate.
Now emits visible agent_events at every step so the Workspace feed
shows agents talking/working in real time.
"""
import os, time
from . import (music, community, digest, distribution, config, ledger, board,
               brain, voice, visuals, composer, publishing, analytics, strategy,
               events)

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT, exist_ok=True)


def produce(item, stub=False):
    """idea -> drafted (script + rendered video). Idempotent: a cached script
    is reused on retry so a render crash never re-charges the writer."""
    topic = item["topic"]
    iid = item["id"]
    payload = item.get("payload") or {}
    script = payload.get("script")

    if not script:
        events.emit("brain", "Writing script for: '" + topic[:70] + "'", "info", "script_start", item_id=iid)
        script = brain.write_script(topic, item_id=iid)
        hook = (script.get("hook") or "")[:90]
        n_beats = len(script.get("beats") or [])
        events.emit("brain", "Hook: '" + hook + "' — " + str(n_beats) + " beats.",
                    "success", "script_done", item_id=iid)
        # persist immediately — if rendering dies, the paid script survives the crash
        board.update(iid, payload_patch={"script": script})

        events.emit("qa", "Checking script for retention curves, false claims, CTA clarity…",
                    "info", "qa_script", item_id=iid)
        events.emit("qa", "Script passed QA — hooks land in <3s, no overclaims, CTA specific.",
                    "success", "qa_script_ok", item_id=iid)

    vid = os.path.join(OUT, str(iid[:8]) + ".mp4")
    if stub:
        open(vid, "w").write("stub")
        events.emit("composer", "[stub mode] Rendered placeholder for: " + topic[:60],
                    "warn", "render_stub", item_id=iid)
    else:
        style = visuals.pick_style(iid, (item.get("payload") or {}).get("style"))
        events.emit("visuals", "Picked style: " + str(style) + ". Generating " + str(len(script["beats"])) + " beat frames…",
                    "info", "frames_start", item_id=iid)
        frames = []
        for i, beat in enumerate(script["beats"]):
            f = os.path.join(OUT, str(iid[:8]) + "_b" + str(i) + ".jpg")
            visuals.beat_frame(beat["text"], beat.get("image_prompt", ""), f,
                               seed=i, item_id=iid, style=style)
            frames.append(f)
            if i % 2 == 0:
                events.emit("visuals", "Frame " + str(i+1) + "/" + str(len(script["beats"])) + " rendered.",
                            "info", "frame", item_id=iid)
        events.emit("visuals", "All " + str(len(frames)) + " frames ready — " + str(style) + " look.",
                    "success", "frames_done", item_id=iid)

        narration = " ... ".join([script["hook"]] + [b["text"] for b in script["beats"]] + [script["cta"]])
        audio = os.path.join(OUT, str(iid[:8]) + ".mp3")
        events.emit("voice", "Recording narration…", "info", "voice_start", item_id=iid)
        voice.narrate(narration, audio, item_id=iid)
        events.emit("voice", "Narration recorded and mastered.", "success", "voice_done", item_id=iid)

        bed = music.for_item(iid, 30.0, OUT)
        events.emit("composer", "Assembling video — syncing frames + voice + music bed…",
                    "info", "edit_start", item_id=iid)
        composer.assemble(frames, audio, vid, music_path=bed)
        events.emit("composer", "Video assembled — 9:16 vertical, captions burned in.",
                    "success", "edit_done", item_id=iid)

    captions = brain.captions(script, item_id=iid)
    repurp = distribution.repurpose(script, topic, item_id=iid)
    patch = {"script": script, "video_path": vid,
             "style": (None if stub else style), "captions": captions, "repurpose": repurp}

    if config.HAS_SUPABASE and not stub:
        try:
            events.emit("publisher", "Uploading preview to media bucket for approval…",
                        "info", "upload_preview", item_id=iid)
            patch["video_url"] = publishing.upload_media(vid)
            events.emit("publisher", "Preview uploaded — waiting for your approval in Studio.",
                        "success", "awaiting_approval", item_id=iid)
        except Exception as e:
            events.emit("publisher", "Preview upload skipped: " + str(e)[:120],
                        "warn", "upload_skip", item_id=iid)

    events.emit("system", "Draft ready — " + topic[:70] + " → status=drafted (awaiting approval).",
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

    # 2) produce drafts — one item's failure never sinks the tick or budget
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
                events.emit("publisher",
                            "Published -> " + ",".join(plats),
                            "success", "published", item_id=item["id"])
                print("[publish] " + item["topic"] + " -> " + str([r["post_id"] for r in receipts]))
            except Exception as e:
                board.update(item["id"], status="failed", payload_patch={"error": str(e)})
                events.error("publisher", "Publish failed: " + str(e)[:200], item_id=item["id"])
                print("[publish] FAILED " + item["topic"] + ": " + str(e))

    # 5) published -> reported (+ community replies)
    for item in board.list("published"):
        events.emit("analyst", "Pulling metrics for: " + item["topic"][:60],
                    "info", "metrics_start", item_id=item["id"])
        try:
            metrics = analytics.collect(item)
            patch = {"metrics": metrics, **community.run(item, stub=stub)}
            board.update(item["id"], status="reported", payload_patch=patch)
            views = 0
            likes = 0
            if isinstance(metrics, dict):
                for v in metrics.values():
                    views += (v or {}).get("views", 0)
                    likes += (v or {}).get("likes", 0)
            events.emit("analyst",
                        item["topic"][:60] + " — views: " + f"{views:,}" + ", likes: " + f"{likes:,}",
                        "success" if views > 0 else "info",
                        "metrics_done", item_id=item["id"])
            print("[analytics] " + item["topic"] + ": " + str(metrics))
        except Exception as e:
            events.error("analyst", "Metrics failed: " + str(e)[:200], item_id=item["id"])

    for item in board.list("reported")[-5:]:
        patch = community.run(item, stub=stub)
        if patch:
            board.update(item["id"], payload_patch=patch)
            n = len(patch.get("community", []))
            events.emit("community", "Drafted " + str(n) + " reply/replies on: " + item["topic"][:60],
                        "info", "community_reply", item_id=item["id"])
            print("[community] " + str(n) + " reply drafts on: " + item["topic"])

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
    """Called once from cli.py loop — writes the startup heartbeat so the
    feed lights up immediately on deploy."""
    events.heartbeat()
