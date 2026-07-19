#!/usr/bin/env python3
"""cli.py — your control seat.
  status | plan [N] | tick [--stub] | board [status] | approve <id> | reject <id>
  generate "topic" | report | loop [--interval SEC]"""
import sys, time
sys.path.insert(0, ".")
from agent import digest, config, board, strategy, orchestrator, ledger, events

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print("Capabilities:\n" + config.capability_report())
        counts = {}
        for i in board.list():
            counts[i["status"]] = counts.get(i["status"], 0) + 1
        print("Board:", counts or "(empty)")
        print("Spent today: $" + f"{ledger.spent_today():.4f}")
    elif cmd == "demo":
        # Zero-key turnkey: one finished, styled, music-backed vertical video.
        topic = " ".join(sys.argv[2:]) or "The free AI tool that writes your emails in your voice"
        events.heartbeat()
        item = board.add(topic, payload={"bucket": "experiment"})
        print("~ demo: producing one video for: " + topic)
        orchestrator.produce(item, stub=False)
        fresh = board.get(item["id"])
        print("~ done -> " + fresh["payload"]["video_path"])
        print("~ style: " + str(fresh["payload"].get("style")) + " | hook: " + fresh["payload"]["script"]["hook"][:70])
        print("~ open the file, judge it like a viewer. This is what the Studio queues daily.")
    elif cmd == "plan":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        for t in strategy.plan(n):
            topic, bucket = t["topic"], t["bucket"]
            print("queued [" + str(bucket) + "]:", board.add(topic, payload={"bucket": bucket})["topic"])
    elif cmd == "digest":
        print(digest.run(force=True))
    elif cmd == "tick":
        orchestrator.tick(stub="--stub" in sys.argv)
    elif cmd == "board":
        st = sys.argv[2] if len(sys.argv) > 2 else None
        for i in board.list(st):
            print(i["id"][:8] + "  " + i["status"].ljust(10) + " " + i["topic"])
    elif cmd == "approve":
        i = _find(sys.argv[2]); board.update(i["id"], status="approved"); print("approved:", i["topic"])
    elif cmd == "reject":
        i = _find(sys.argv[2]); board.update(i["id"], status="rejected"); print("rejected:", i["topic"])
    elif cmd == "generate":
        item = board.add(sys.argv[2]); orchestrator.produce(item)
        print("video:", board.get(item["id"])["payload"]["video_path"])
    elif cmd == "report":
        for i in board.list("reported"):
            print(i["topic"] + ": " + str(i["payload"].get("metrics")))
    elif cmd == "loop":
        iv = int(sys.argv[sys.argv.index("--interval") + 1]) if "--interval" in sys.argv else 60
        # Boot heartbeat so the feed lights up within seconds of a deploy
        try:
            orchestrator.boot()
        except Exception as e:
            print("[boot] heartbeat failed (non-fatal):", e)
        print("=" * 60)
        print("Agent-X v4.3 pipeline ONLINE")
        print("  18 agents loaded: scout🔭 research🔎 architect🏛️ strategist📋 planner📅 brain✍️")
        print("                   visuals🎨 voice🎙️ composer🎬 qa🔍 grader🎯 seo🔖 publisher📤")
        print("                   analyst📊 community💬 digest📬 budget💰 system⚙️")
        print("  Quality gate: 8/10 across hook/visuals/pacing/audio/caption/CTA")
        print("  Budget cap: $DAILY_BUDGET_USD/day  (KILL_SWITCH=1 to pause)")
        print("=" * 60)
        print("[loop] starting tick loop every", iv, "seconds")
        while True:
            try:
                orchestrator.tick()
            except Exception as e:
                # never let a single tick error kill the whole loop
                print("[loop] tick error:", e)
                try:
                    events.error("system", "Tick error: " + str(e)[:200])
                except Exception:
                    pass
            time.sleep(iv)
    else:
        print(__doc__)

def _find(prefix):
    for i in board.list():
        if i["id"].startswith(prefix):
            return i
    raise SystemExit("no item " + prefix)

if __name__ == "__main__":
    main()
