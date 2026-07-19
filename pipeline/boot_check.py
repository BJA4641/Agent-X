#!/usr/bin/env python3
"""boot_check.py — runs BEFORE the main CMD in Docker.

Imports every agent module one at a time so the Railway logs show the EXACT
module that fails (instead of a misleading cascade like "cannot import memory").
Exits 0 only if ALL imports succeed; otherwise prints the traceback and exits 1.
"""
import sys, os, traceback, importlib

# Match cli.py's sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    "agent.config", "agent.ledger", "agent.events", "agent.llm",
    "agent.memory", "agent.board", "agent.projects",
    "agent.scout", "agent.research", "agent.architect",
    "agent.strategy", "agent.strategist", "agent.planner",
    "agent.brain", "agent.visuals", "agent.voice", "agent.captions",
    "agent.overlays", "agent.sfx", "agent.music", "agent.composer",
    "agent.qa", "agent.grader", "agent.seo", "agent.publishing",
    "agent.analytics", "agent.community", "agent.digest",
    "agent.distribution", "agent.connections",
    "agent.niches", "agent.brand",
    "agent.orchestrator",
]

def main():
    print("=" * 60)
    print("Agent-X BOOT CHECK — importing all 18+ agent modules…")
    print("=" * 60)
    failed = []
    for m in MODULES:
        try:
            importlib.import_module(m)
            print(f"  OK   {m}")
        except Exception as e:
            print(f"  FAIL {m}: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed.append(m)
    print("-" * 60)
    if failed:
        print(f"BOOT CHECK FAILED on: {failed}")
        print("Fix the failing module above and redeploy.")
        sys.exit(1)
    print(f"BOOT CHECK OK — all {len(MODULES)} modules imported cleanly.")

    # Sanity: try the key top-level import cli.py does
    try:
        from agent import digest, config, board, strategy, orchestrator, ledger, events
        print("Top-level cli.py import OK.")
    except Exception as e:
        print(f"Top-level import FAILED: {e}")
        traceback.print_exc()
        sys.exit(2)

if __name__ == "__main__":
    main()
