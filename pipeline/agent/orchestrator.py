"""orchestrator.py — one tick = one pass of the whole company.
Respects kill switch and budget; pauses at YOUR approval gate."""
import os, time
from . import music, community, digest, distribution, config, ledger, board, brain, voice, visuals, composer, publishing, analytics, strategy

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(OUT, exist_ok=True)

def produce(item, stub=False):
    """idea -> drafted (script + rendered video). Idempotent: a cached script is reused
    on retry so a render crash never re-charges the writer."""
    payload = item.get("payload") or {}
    script = payload.get("script")
    if not script:
        script = brain.write_script(item["topic"], item_id=item["id"])
        # persist immediately — if rendering dies, the paid script survives the crash
        board.update(item["id"], payload_patch={"script": script})
    vid = os.path.join(OUT, f"{item['id'][:8]}.mp4")
    if stub:
        open(vid, "w").write("stub")
    else:
        style = visuals.pick_style(item["id"], (item.get("payload") or {}).get("style"))
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
    patch = {"script": script, "video_path": vid, "style": (None if stub else style), "captions": brain.captions(script, item_id=item["id"]),
             "repurpose": distribution.repurpose(script, item["topic"], item_id=item["id"])}
    if config.HAS_SUPABASE and not stub:
        try:  # browser-viewable preview for the Studio approval page
            patch["video_url"] = publishing.upload_media(vid)
        except Exception as e:
            print(f"[content] preview upload skipped: {e}")
    return board.update(item["id"], status="drafted", payload_patch=patch)

def tick(stub=False):
    if config.kill_switch_on():
        print("KILL SWITCH ON — tick refused."); return
    # 1) plan if the idea queue is low
    if len(board.list("idea")) == 0 and len(board.list("drafted")) < config.BATCH_SIZE:
        for t in strategy.plan():
            t, bucket = t["topic"], t["bucket"]
            board.add(t, payload={"bucket": bucket})
            print(f"[strategy] queued: {t}")
    # 2) produce drafts — one item's failure can NEVER sink the tick or loop the budget
    for item in board.list("idea")[: config.BATCH_SIZE]:
        print(f"[content] producing: {item['topic']}")
        try:
            produce(item, stub=stub)
        except Exception as e:
            attempts = (item.get("payload") or {}).get("attempts", 0) + 1
            detail = f"attempt {attempts}: {str(e)[:300]}"
            ledger.record("produce", ok=False, detail=detail, item_id=item["id"])
            if attempts >= 3:
                board.update(item["id"], status="failed", payload_patch={"attempts": attempts, "error": detail})
                print(f"[content] FAILED after {attempts} attempts: {item['topic']} — {detail}")
            else:
                board.update(item["id"], payload_patch={"attempts": attempts})
                print(f"[content] attempt {attempts} failed, will retry: {detail}")
    # 3) approved -> scheduled (next slot, 1/day starting now)
    for i, item in enumerate(board.list("approved")):
        board.update(item["id"], status="scheduled", scheduled_at=int(time.time()) + i * 86400)
        print(f"[producer] scheduled: {item['topic']}")
    # 4) due + scheduled -> publish
    for item in board.list("scheduled"):
        if item["scheduled_at"] and int(item["scheduled_at"] if isinstance(item["scheduled_at"], (int, float)) else 0) <= time.time():
            caps = item["payload"].get("captions", {})
            ig = caps.get("instagram", {})
            caption = (ig.get("caption") or item["payload"]["script"]["hook"] + " " + item["payload"]["script"]["cta"])
            if ig.get("hashtags"): caption += "\n\n" + " ".join("#" + h for h in ig["hashtags"])
            try:
                receipts = publishing.publish(item, caption)
                board.update(item["id"], status="published", payload_patch={"publish_receipts": receipts})
                print(f"[publish] {item['topic']} -> {[r['post_id'] for r in receipts]}")
            except Exception as e:
                board.update(item["id"], status="failed", payload_patch={"error": str(e)})
                print(f"[publish] FAILED {item['topic']}: {e}")
    # 5) published -> reported (+ community pass drafts replies to new comments)
    for item in board.list("published"):
        metrics = analytics.collect(item)
        patch = {"metrics": metrics, **community.run(item, stub=stub)}
        board.update(item["id"], status="reported", payload_patch=patch)
        print(f"[analytics] {item['topic']}: {metrics}")
    for item in board.list("reported")[-5:]:
        patch = community.run(item, stub=stub)
        if patch:
            board.update(item["id"], payload_patch=patch)
            print(f"[community] {len(patch['community'])} reply drafts on: {item['topic']}")
    # 6) weekly digest
    digest.run()
    print(f"[ledger] spent today: ${ledger.spent_today():.4f} / ${config.DAILY_BUDGET_USD:.2f}")
