"""workers/runner.py — entry point for the v5 worker pool.

Boots the runtime, registers all department handlers onto a single Worker
and runs forever. This is what the new Docker CMD will point at.

We deliberately use ONE worker process for Phase 2 MVP to match the user's
mandate "start with ONE active account, stop burning money" — a single
worker processing one job at a time keeps spend predictable and logs
legible. We'll split into multiple Railway services in Phase 3.
"""
from __future__ import annotations
import os, sys, time, traceback

# Ensure pipeline/ is on sys.path (matches cli.py)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentcore.runtime import get_runtime
from agentcore import Worker, Job, EventType, Priority, kill_switch_on
from workers.departments import register_all


def main():
    rt = get_runtime()
    # One worker handles all job types in Phase 2 MVP
    worker = Worker(rt.queue, name="agentx-v5", poll_interval=3.0)
    worker.set_deps(**rt.deps)
    register_all(worker)

    # Seed the boot job — this kicks off the tick loop (portfolio.tick will
    # self-schedule via _schedule_next_tick, so the system survives restarts).
    rt.queue.enqueue(Job(
        job_type="portfolio.boot",
        payload={"booted_at": time.time(), "version": "5.0"},
        priority=Priority.HIGH,
        idempotency_key=f"boot:{int(time.time()//60)}",
    ))

    print("=" * 60)
    print("Agent-X v5 pipeline ONLINE (blueprint-driven worker)")
    print(f"  tenant:    {rt.deps.get('tenant_id', os.environ.get('TENANT_ID','me'))}")
    print(f"  budget:    ${rt.deps.get('daily_budget', os.environ.get('DAILY_BUDGET_USD','1.50'))}")
    print(f"  kill:      {'ON (PAUSED)' if kill_switch_on() else 'off'}")
    print(f"  handlers:  {list(worker.handlers.keys())}")
    print("=" * 60)

    try:
        worker.run_forever()
    except KeyboardInterrupt:
        print("[runner] stopped by keyboard")
        worker.stop()


if __name__ == "__main__":
    main()
