#!/usr/bin/env python3
"""cli.py v5 — control seat for Agent-X.

Commands:
  status        capability report + board state + spend
  demo <topic>  zero-key demo render of one video (legacy path)
  plan [N]      enqueue N fresh ideas on the legacy board
  tick [--stub] one tick of the legacy orchestrator
  board [stat]  list board items
  approve <id>  mark item approved
  reject <id>   mark item rejected
  generate <t>  legacy one-shot generate+render
  report        list reported items with metrics
  digest        print daily digest
  loop [--interval S]   LEGACY loop (v4.3 orchestrator.tick)
  worker        v5 BLUEPRINT WORKER (JobQueue + event bus + departments)
  bootcheck     run boot_check.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _legacy_imports():
    from agent import digest, config, board, strategy, orchestrator, ledger, events
    return digest, config, board, strategy, orchestrator, ledger, events


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "worker":
        # v5 blueprint worker — event-driven, job-queue backed, department org.
        from workers.runner import main as runner_main
        runner_main()
        return

    if cmd == "bootcheck":
        import boot_check
        boot_check.main()
        return

    digest, config, board, strategy, orchestrator, ledger, events = _legacy_imports()

    if cmd == "status":
        print("Capabilities:\n" + config.capability_report())
        counts = {}
        for i in board.list():
            counts[i["status"]] = counts.get(i["status"], 0) + 1
        print("Board:", counts or "(empty)")
        print("Spent today: $" + f"{ledger.spent_today():.4f}")
    elif cmd == "demo":
        topic = " ".join(sys.argv[2:]) or "The free AI tool that writes your emails in your voice"
        events.heartbeat()
        item = board.add(topic, payload={"bucket": "experiment"})
        print("~ demo: producing one video for: " + topic)
        orchestrator.produce(item, stub=False)
        fresh = board.get(item["id"])
        if fresh and fresh.get("payload", {}).get("video_path"):
            print("~ done -> " + fresh["payload"]["video_path"])
            print("~ style: " + str(fresh["payload"].get("style")) +
                  " | hook: " + fresh["payload"]["script"]["hook"][:70])
        else:
            print("~ demo finished (no video path set — check logs)")
    elif cmd == "plan":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else None
        for t in strategy.plan(n):
            topic, bucket = t["topic"], t["bucket"]
            print("queued [" + str(bucket) + "]:",
                  board.add(topic, payload={"bucket": bucket})["topic"])
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
        out = board.get(item["id"])
        if out:
            print("video:", out["payload"].get("video_path"))
    elif cmd == "report":
        for i in board.list("reported"):
            print(i["topic"] + ": " + str(i["payload"].get("metrics")))
    elif cmd == "loop":
        iv = int(sys.argv[sys.argv.index("--interval") + 1]) if "--interval" in sys.argv else 60
        try:
            orchestrator.boot()
        except Exception as e:
            print("[boot] heartbeat failed (non-fatal):", e)
        print("=" * 60)
        print("Agent-X v4.3 LEGACY loop (use 'worker' for v5 blueprint engine)")
        print("=" * 60)
        while True:
            try:
                orchestrator.tick()
            except Exception as e:
                print("[loop] tick error:", e)
                try:
                    events.error("system", "Tick error: " + str(e)[:200])
                except Exception:
                    pass
            time.sleep(iv)
    else:
        print(__doc__)


def _find(prefix):
    from agent import board
    for i in board.list():
        if i["id"].startswith(prefix):
            return i
    raise SystemExit("no item " + prefix)


if __name__ == "__main__":
    main()
