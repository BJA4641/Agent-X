"""orchestrator.py — one tick = one pass of the whole company.
Respects kill switch and budget; pauses at YOUR approval gate.
v1.5: QA is REAL now — qa.review() runs on every fresh script BEFORE we pay
for a render; a rejected script gets one revision pass with the editor's fix
note, and the verdict (score + note) is stored on the item so the Studio can
show it. The Trend Scout runs every ~30 min and fills the trends desk.
Every step still emits honest agent_events for the Workspace feed.
"""
import os, time
from . import (music, community, digest, distribution, config, ledger, board,
               brain, voice, visuals, composer, publishing, analytics, strategy,
               events, qa, scout, projects)

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT, exist_ok=True)


def _qa_gate(script, topic, iid):
    """Run the real editor-in-chief on a fresh script. One revision round max.
    Returns (script, verdict). Never raises — a QA crash passes the draft to
    the human gate with an honest 'QA errored' event."""
    platforms = ["instagram"] + (["youtube"] if config.HAS_YT else [])
    try:
        events.emit("qa", "Reviewing script — retention curve, claims, CTA, brand fit…",
                    "info", "qa_start", item_id=iid)
        verdict = qa.review(script, {}, None, platforms, item_id=iid)
        if verdict.get("approved"):
            sc = verdict.get("score")
            events.emit("qa", "Script APPROVED" + ((" — score " + str(sc) + "/10.") if sc else "."),
                        "success", "qa_ok", item_id=iid)
            return script, verdict

        fix = str(verdict.get("fix_instruction") or verdict.get("reason") or "tighten the hook")[:180]
        events.debate("qa", "Script REJECTED: " + fix, item_id=iid)
        if verdict.get("escalated"):
            return script, verdict  # human gate will see the flag

        events.emit("brain", "Rewriting per QA note: " + fix, "warn", "revise", item_id=iid)
        revised = brain.write_script(
            topic + "\n\nEDITOR'S MANDATORY REVISION NOTE (fix this): " + fix, item_id=iid)
        if revised.get("hook") and revised.get("beats"):
            script = revised
        verdict2 = qa.review(script, {}, None, platforms, item_id=iid, rounds_so_far=1)
        if verdict2.get("approved"):
            events.emit("qa", "Revision APPROVED — score "
                        + str(verdict2.get("score", "?")) + "/10.", "success", "qa_ok", item_id=iid)
        else:
            events.debate("qa", "Still not perfect after revision — flagging for your human review: "
                          + str(verdict2.get("reason") or verdict2.get("fix_instruction") or "")[:150],
                          item_id=iid)
        return script, verdict2
    except Exception as e:
        events.emit("qa", "QA errored (" + str(e)[:80] + ") — draft goes to your human gate unscored.",
                    "warn", "qa_err", item_id=iid)
        return script, {"approved": True, "auto_passed_due_to_error": True}


def produce(item, stub=False):
    """idea -> drafted (script + rendered video). Idempotent: a cached script
    is reused on retry so a render crash never re-charges the writer."""
    topic = item["topic"]
    iid = item["id"]
    payload = item.get("payload") or {}
    script = payload.get("script")
    qa_verdict = payload.get("qa")

    if not script:
        events.emit("brain", "Writing script for: '" + topic[:70] + "'", "info", "script_start", item_id=iid)
        ctxbits = []
        if payload.get("niche"):
            ctxbits.append("Project niche: " + str(payload["niche"]))
        if payload.get("project"):
            ctxbits.append("Brand/project: " + str(payload["project"]))
        if payload.get("source") and str(payload["source"]).startswith("http"):
            ctxbits.append("Trend source URL (angle only, don't quote it): " + str(payload["source"]))
        script = brain.write_script(topic, item_id=iid, context=("\n".join(ctxbits) or None))
        hook = (script.get("hook") or "")[:90]
        n_beats = len(script.get("beats") or [])
        events.emit("brain", "Hook: '" + hook + "' — " + str(n_beats) + " beats.",
                    "success", "script_done", item_id=iid)

        # REAL QA gate — before we spend a render on it
        script, verdict = _qa_gate(script, topic, iid)
        qa_verdict = {"approved": bool(verdict.get("approved")),
                      "score": verdict.get("score"),
                      "note": (verdict.get("fix_instruction") or verdict.get("reason") or None),
                      "auto_passed": bool(verdict.get("auto_passed_due_to_error"))}

        # persist immediately — if rendering dies, the paid script survives the crash
        board.update(iid, payload_patch={"script": script, "qa": qa_verdict})

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
        events.emit("composer", "Video assembled — 9:16 vertical.",
                    "success", "edit_done", item_id=iid)

    captions = brain.captions(script, item_id=iid)
    repurp = distribution.repurpose(script, topic, item_id=iid)
    patch = {"script": script, "video_path": vid, "qa": qa_verdict,
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

    # 0) trend scout — free, throttled to ~1 pass / 30 min, never sinks the tick
    try:
        scout.maybe_run()
    except Exception as e:
        events.emit("scout", "Scout pass crashed (non-fatal): " + str(e)[:120], "warn", "scout_err")

    # 1) plan if the idea queue is low
    ideas = board.list("idea")
    if len(ideas) == 0 and len(board.list("drafted")) < config.BATCH_SIZE:
        # v1.6: plan PER ACTIVE PROJECT — one account, several niches at once.
        # Budget still rules: strategy.plan() checks ledger.budget_ok internally,
        # so extra projects never blow past your daily cap.
        for proj in projects.active_projects():
            pname = str(proj.get("name") or "default")
            niche = proj.get("niche")
            events.emit("strategy", "Queue low — planning for project '" + pname + "'"
                        + ((" · " + niche) if niche else "") + " from winners, trends & competitors…",
                        "info", "planning")
            try:
                planned = strategy.plan(niche=niche)
                for t in planned:
                    topic = t["topic"]
                    bucket = t.get("bucket", "proven")
                    board.add(topic, payload={"bucket": bucket, "project_id": proj.get("id"),
                                              "project": pname, "niche": niche})
                    events.emit("strategy", "Queued [" + pname + " · " + str(bucket) + "]: " + topic[:80],
                                "success", "idea_queued")
            except Exception as e:
                events.error("strategy", "Planning failed for '" + pname + "': " + str(e)[:200])

    # 2) produce drafts — one item's failure never sinks the tick or budget
    idea_items = board.list("idea")[: config.BATCH_SIZE]
    if not idea_items:
        events.idle_chatter({
            "drafted": len(board.list("drafted")),
            "scheduled": len(board.list("scheduled")),
            "published": len(board.list("published")),
            "spent": ledger.spent_today(), "budget": ledger.daily_budget(),
            "scout_at": config.get_setting("scout_last_ts"),
        })
    for item in idea_items:
        events.emit("brain", "Picking up: " + item["topic"][:75],
                    "info", "pickup", item_id=item["id"])
        try:
            produce(item, stub=stub)
            try:  # v1.6: stamp the TRUE cost of this draft onto the item
                c = ledger.item_cost(item["id"])
                if c:
                    board.update(item["id"], payload_patch={"cost_usd": round(c, 4)})
                    events.emit("budget", "Draft cost: $" + f"{c:.4f}" + " — " + item["topic"][:55],
                                "info", "item_cost", item_id=item["id"], cost_usd=0)
            except Exception:
                pass
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

    # v1.6 opt-in: WEEKLY_PLANNER=1 lets the planner fill next week's calendar
    # once every ~7 days (real cost: it queues up to a week of ideas — off by default).
    if os.environ.get("WEEKLY_PLANNER") == "1":
        try:
            from . import planner
            last = (config.get_setting("planner_last_ts") or {}).get("ts", 0)
            if time.time() - float(last or 0) > 6.5 * 86400:
                events.emit("planner", "Weekly planner engaged — drafting next week's calendar…",
                            "info", "plan_week")
                planner.build_week_plan(config.TENANT_ID)
                config.set_setting("planner_last_ts", {"ts": time.time()})
                events.emit("planner", "Week planned — review the queue in Studio.", "success", "plan_week_done")
        except Exception as e:
            events.error("planner", "Weekly planning failed: " + str(e)[:200])

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
