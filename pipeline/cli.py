#!/usr/bin/env python3
"""cli.py — your control seat.
  status | plan [N] | tick [--stub] | board [status] | approve <id> | reject <id>
  generate "topic" | report | loop [--interval SEC]"""
import sys, time
sys.path.insert(0, ".")
from agent import digest, config, board, strategy, orchestrator, ledger

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print("Capabilities:\n" + config.capability_report())
        counts = {}
        for i in board.list():
            counts[i["status"]] = counts.get(i["status"], 0) + 1
        print("Board:", counts or "(empty)")
        print(f"Spent today: ${ledger.spent_today():.4f}")
    elif cmd == "demo":
        # Zero-key turnkey: one finished, styled, music-backed vertical video on your machine.
        # Real script if ANTHROPIC_API_KEY is set; free edge-tts voice; Gemini visuals if keyed, styled art otherwise.
        topic = " ".join(sys.argv[2:]) or "The free AI tool that writes your emails in your voice"
        item = board.add(topic, payload={"bucket": "experiment"})
        print(f"~ demo: producing one video for: {topic}")
        orchestrator.produce(item, stub=False)
        fresh = board.get(item["id"])
        print(f"~ done -> {fresh['payload']['video_path']}")
        print(f"~ style: {fresh['payload'].get('style')} | hook: {fresh['payload']['script']['hook'][:70]}")
        print("~ open the file, judge it like a viewer. This is what the Studio queues daily.")
    elif cmd == "plan":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        for t in strategy.plan(n):
            topic, bucket = t["topic"], t["bucket"]
            print(f"queued [{bucket}]:", board.add(topic, payload={"bucket": bucket})["topic"])
    elif cmd == "digest":
        print(digest.run(force=True))
    elif cmd == "tick":
        orchestrator.tick(stub="--stub" in sys.argv)
    elif cmd == "board":
        st = sys.argv[2] if len(sys.argv) > 2 else None
        for i in board.list(st):
            print(f"{i['id'][:8]}  {i['status']:<10} {i['topic']}")
    elif cmd == "approve":
        i = _find(sys.argv[2]); board.update(i["id"], status="approved"); print("approved:", i["topic"])
    elif cmd == "reject":
        i = _find(sys.argv[2]); board.update(i["id"], status="rejected"); print("rejected:", i["topic"])
    elif cmd == "generate":
        item = board.add(sys.argv[2]); orchestrator.produce(item)
        print("video:", board.get(item["id"])["payload"]["video_path"])
    elif cmd == "report":
        for i in board.list("reported"):
            print(f"{i['topic']}: {i['payload'].get('metrics')}")
    elif cmd == "loop":
        iv = int(sys.argv[sys.argv.index("--interval") + 1]) if "--interval" in sys.argv else 300
        while True:
            orchestrator.tick(); time.sleep(iv)
    else:
        print(__doc__)

def _find(prefix):
    for i in board.list():
        if i["id"].startswith(prefix):
            return i
    raise SystemExit(f"no item {prefix}")

if __name__ == "__main__":
    main()
