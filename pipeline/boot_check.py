#!/usr/bin/env python3
"""boot_check.py v5 — runs BEFORE the main CMD in Docker.

Imports every agent module + the new v5 worker modules one at a time so
Railway logs show the EXACT module that fails. Exits 0 only if ALL imports
succeed.
"""
import sys, os, traceback, importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    # core config
    "agent.config", "agent.ledger", "agent.events", "agent.llm",
    "agent.memory", "agent.board", "agent.projects",
    # legacy creative stack (proven production code)
    "agent.scout", "agent.research", "agent.architect",
    "agent.strategy", "agent.strategist", "agent.planner",
    "agent.brain", "agent.visuals", "agent.voice", "agent.captions",
    "agent.overlays", "agent.sfx", "agent.music", "agent.composer",
    "agent.qa", "agent.grader", "agent.seo", "agent.publishing",
    "agent.analytics", "agent.community", "agent.digest",
    "agent.distribution", "agent.connections",
    "agent.niches", "agent.brand",
    "agent.orchestrator",
    # agentcore primitives
    "agentcore",
    "agentcore.config", "agentcore.models", "agentcore.bus",
    "agentcore.jobs", "agentcore.llm", "agentcore.guards",
    "agentcore.observability", "agentcore.validators",
    "agentcore.agent", "agentcore.worker",
    "agentcore.ledger", "agentcore.memory", "agentcore.events",
    "agentcore.runtime",
    # v5 workers
    "workers",
    "workers.common", "workers.runner",
    "workers.departments",
    "workers.departments.finance",
    "workers.departments.cqo",
    "workers.departments.risk",
    "workers.departments.portfolio",
    "workers.departments.research",
    "workers.departments.editorial",
    "workers.departments.creative",
    "workers.departments.postprod",
    "workers.departments.distribution",
    "workers.departments.analytics",
    "workers.departments.knowledge",
]


def main():
    print("=" * 60)
    print("Agent-X v5 BOOT CHECK — importing all modules…")
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

    # Sanity check: top-level CLI import
    try:
        import cli
        print("cli.py import OK.")
    except Exception as e:
        print(f"cli.py import FAILED: {e}")
        traceback.print_exc()
        sys.exit(2)

    # Sanity: agentcore exports
    try:
        from agentcore import (Job, JobStatus, Bus, Worker, BaseAgent,
                                Tracer, Script, GradeResult, Beat, SEOPack,
                                ModelRouter, JobQueue, get_runtime)
        print("agentcore public API OK.")
    except Exception as e:
        print(f"agentcore API FAILED: {e}")
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
