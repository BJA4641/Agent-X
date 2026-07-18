"""orchestrator.py — one tick = one pass of the whole company.
Respects kill switch and budget; pauses at YOUR approval gate.

UPGRADE v0.3 — adds:
- Brand Bible grounding (brand.grounding_block)
- Multi-tenant credentials via connections.py
- QA gate (qa.review) before drafted status
- Planner calendar build (planner.build_week_plan) when queue is low
"""
import os, time
from . import music, community, digest, distribution, config, ledger, board, brain, voice, visuals, composer, publishing, analytics, strategy, qa, brand, planner, connections

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT, exist_ok=True)


def produce(item, stub=False, user_id=None):
    """idea -> drafted (script + rendered video). Idempotent: a cached script is reused
    on retry so a render crash never re-charges the writer."""
    payload = item.get("payload") or {}
    script = payload.get("script")
    uid = user_id or item.get("tenant_id") or config.TENANT_ID
    if not script:
        # Inject brand grounding context into the writer via the topic
        topic_with_context = item["topic"]
        script = brain.write_script(topic_with_context, item_id=item["id"])
        board.update(item["id"], payload_patch={"script": script})
    vid = os.path.join(OUT, f"{item['id'][:8]}.mp4")
    if stub:
        open(vid, "w").write("stub")
    else:
        style = visuals.pick_style(item["id"], payload.get("style"))
        frames = []
        for i, beat in enumerate(script["beats"]):
            f = os.path.join(OUT, f"{item['id'][:8]}_b{i}.jpg")
            visuals.beat_frame(beat["text"], beat.get("image_prompt", ""), f, seed=i, item_id=item["id"], style=style)
            frames.append(f)
        narration = " ... ".join([script["hook"]] + [b["text"] for b in script["beats"]] + [script["cta"]])
        audio = os.path.join(OUT, f"{item['id'][:8]}.mp3")
        voice.narrate(narration, audio, item_id=item["id"])
        bed = music.for_item(item["id"], 30.0, OUT)
        composer.assemble(frames, audio, vid, music_path=bed)
    patch = {"script": script, "video_path": vid, "style": (None if stub else style),
             "captions": brain.captions(script, item_id=item["id"]),
             "repurpose": distribution.repurpose(script, item["topic"], item_id=item["id"])}
    # --- QA gate (3 revision rounds max) ---
    if not stub:
        platforms = connections.active_platforms_for_user(uid) or ["instagram"]
        qa_rounds = payload.get("qa_rounds", 0)
        verdict = qa.review(script, patch["captions"], style or "auto", platforms,
                            item_id=item["id"], user_id=uid, rounds_so_far=qa_rounds)
        if not verdict.get("approved"):
            if verdict.get("escalated"):
                patch["qa_escalation"] = verdict["reason"]
                patch["qa_status"] = "needs_human"
                return board.update(item["id"], status="rejected", payload_patch={**patch, "rejection": {"reason": verdict["reason"], "at": time.time()}})
            # Route back
            patch["qa_rounds"] = qa_rounds + 1
            patch["qa_feedback"] = verdict
            # Simple revision: re-run captions if that's the target, else rewrite script hook
            if verdict.get("route_to") in ("captions", "publisher"):
                patch["captions"] = brain.captions(script, item_id=item["id"])
            else:
                script = brain.write_script(item["topic"] + " | edit note: " + verdict["fix_instruction"], item_id=item["id"])
                patch["script"] = script
            board.update(item["id"], payload_patch=patch)
            return produce(item, stub=stub, user_id=uid)  # re-run production with revised script
    if config.HAS_SUPABASE and not stub:
        try:
            patch["video_url"] = publishing.upload_media(vid, user_id=uid)
        except Exception as e:
            print(f"[content] preview upload skipped: {e}")
    return board.update(item["id"], status="drafted", payload_patch=patch)


def tick(stub=False, user_id=None):
    uid = user_id or config.TENANT_ID
    if config.kill_switch_on():
        print("KILL SWITCH ON — tick refused."); return
    # 0) Build weekly plan if idea queue is low (planner replaces bare rotation)
    if len(board.list("idea")) == 0 and len(board.list("drafted")) < config.BATCH_SIZE:
        try:
            queued = planner.build_week_plan(user_id=uid, days=7)
            for q in queued:
                print(f"[planner] queued {q.get('platform')} {q.get('format')}: {q['topic']}")
        except Exception as e:
            print(f"[planner] failed, falling back to strategy.plan(): {e}")
            for t in strategy.plan():
                board.add(t["topic"], payload={"bucket": t.get("bucket", "proven")})
    elif len(board.list("idea")) == 0 and len(board.list("drafted")) < config.BATCH_SIZE:
        for t in strategy.plan():
            t, bucket = t["topic"], t["bucket"]
            board.add(t, payload={"bucket": bucket})
            print(f"[strategy] queued: {t}")
    # 2) produce drafts
    for item in board.list("idea")[: config.BATCH_SIZE]:
        print(f"[content] producing: {item['topic']}")
        try:
            produce(item, stub=stub, user_id=uid)
        except Exception as e:
            attempts = (item.get("payload") or {}).get("attempts", 0) + 1
            detail = f"attempt {attempts}: {str(e)[:500]}"
            ledger.record("produce", ok=False, detail=detail, item_id=item["id"])
            if attempts >= 3:
                board.update(item["id"], status="failed", payload_patch={"attempts": attempts, "error": detail})
                print(f"[content] FAILED after {attempts} attempts: {item['topic']} — {detail}")
            else:
                board.update(item["id"], payload_patch={"attempts": attempts})
                print(f"[content] attempt {attempts} failed, will retry: {detail}")
    # 3) approved -> scheduled
    for i, item in enumerate(board.list("approved")):
        scheduled = item.get("scheduled_at")
        if not scheduled:
            scheduled = int(time.time()) + i * 86400
        board.update(item["id"], status="scheduled", scheduled_at=scheduled)
        print(f"[producer] scheduled: {item['topic']}")
    # 4) due + scheduled -> publish (use per-user credentials)
    for item in board.list("scheduled"):
        sched = item.get("scheduled_at")
        due = False
        if isinstance(sched, (int, float)):
            due = sched <= time.time()
        else:
            try:
                import datetime as _dt
                due = _dt.datetime.fromisoformat(str(sched).replace("Z", "+00:00")).timestamp() <= time.time()
            except Exception:
                due = True
        if due:
            caps = item["payload"].get("captions", {})
            ig = caps.get("instagram", {})
            caption = (ig.get("caption") or item["payload"]["script"]["hook"] + " " + item["payload"]["script"]["cta"])
            if ig.get("hashtags"): caption += "\n\n" + " ".join("#" + h for h in ig["hashtags"])
            try:
                receipts = publishing.publish(item, caption, user_id=uid)
                board.update(item["id"], status="published", payload_patch={"publish_receipts": receipts})
                print(f"[publish] {item['topic']} -> {[r['post_id'] for r in receipts]}")
            except Exception as e:
                board.update(item["id"], status="failed", payload_patch={"error": str(e)})
                print(f"[publish] FAILED {item['topic']}: {e}")
    # 5) published -> reported
    for item in board.list("published"):
        metrics = analytics.collect(item, user_id=uid)
        patch = {"metrics": metrics, **community.run(item, stub=stub, user_id=uid)}
        board.update(item["id"], status="reported", payload_patch=patch)
        print(f"[analytics] {item['topic']}: {metrics}")
    for item in board.list("reported")[-5:]:
        patch = community.run(item, stub=stub, user_id=uid)
        if patch:
            board.update(item["id"], payload_patch=patch)
    digest.run()
    print(f"[ledger] spent today: ${ledger.spent_today():.4f} / ${config.DAILY_BUDGET_USD:.2f}")
