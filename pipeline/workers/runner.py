"""workers/runner.py — v5.1 entry point for the Phase 3-optimized worker pool.

Boots the runtime, registers all department handlers (Phase 2+3) on a single
Worker, seeds self-scheduling bootstrap jobs (heartbeat, snapshot, human_desk,
portfolio tick, first scout run), and runs forever.

Phase 3 optimizations:
  * ops.heartbeat  every 30s → worker_health table (dashboard shows liveness).
  * ops.snapshot   every 1h  → kpi_snapshots for CEO scorecard.
  * human_desk.sync every 20s → surfaces escalations for founder review.
  * Auto-throttle via cfo.preflight (reschedules low-priority work when
    budget >90% spent instead of failing outright).
  * Experiment engine wired (hooks A/B tested, lessons fed back to memory).
  * Single process, single active account — keeps spend predictable.
"""
from __future__ import annotations
import os, sys, time, traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentcore.runtime import get_runtime
from agentcore import Worker, Job, EventType, Priority, kill_switch_on, DAILY_BUDGET_USD
from workers.departments import register_all

VERSION = "5.7.1"  # v5.7: soft-pause (pause intake, finish in-flight), docs library+editor in web, /api/version


def main():
    rt = get_runtime()
    worker = Worker(rt.queue, name="agentx-v5", poll_interval=2.5)
    worker.set_deps(**rt.deps)
    register_all(worker)

    # ---- Bootstrap self-scheduling jobs (idempotent keys prevent dupes after restart) ----
    now = time.time()
    boot_jobs = [
        Job(job_type="portfolio.boot",
            payload={"booted_at": now, "version": VERSION},
            priority=Priority.HIGH,
            idempotency_key=f"boot:{int(now//60)}"),
        Job(job_type="ceo.daily_tick",
            payload={"version": VERSION},
            priority=Priority.HIGH,
            idempotency_key=f"ceoday:{int(now//3600)}"),
        Job(job_type="ops.heartbeat",
            payload={"started_at": now, "version": VERSION},
            priority=Priority.LOW,
            idempotency_key=f"hb:{worker.id}:{int(now//30)}"),
        Job(job_type="ops.snapshot",
            payload={}, priority=Priority.LOW,
            idempotency_key=f"snap:{int(now//3600)}"),
        Job(job_type="human_desk.sync",
            payload={}, priority=Priority.LOW,
            idempotency_key=f"desksync:{int(now//20)}"),
    ]
    for j in boot_jobs:
        rt.queue.enqueue(j)

    print("=" * 60)
    print(f"Agent-X v{VERSION} pipeline ONLINE — CEO ENGINE ACTIVE")
    print(f"  tenant:      {os.environ.get('TENANT_ID','me')}")
    print(f"  budget:      ${DAILY_BUDGET_USD}/day")
    print(f"  kill:        {'ON (PAUSED)' if kill_switch_on() else 'off'}")
    print(f"  CEO mode:    every spend requires CEO approval (ROI-gated)")
    print(f"  autothrottle: ON (reserves 10% of budget, delays low-priority work)")
    print(f"  asset reuse: ON (searches library before generating)")
    print(f"  heartbeat:   every 30s → worker_health")
    print(f"  kpi snapshot: every 1h → kpi_snapshots")
    print(f"  CEO review:  once/day → capital allocation + recommendations")
    print(f"  human desk:  every 20s → escalations")
    print(f"  handlers:    {len(worker.handlers)} jobs")
    print("=" * 60)

    try:
        worker.run_forever()
    except KeyboardInterrupt:
        print("[runner] stopped by keyboard")
        worker.stop()


if __name__ == "__main__":
    main()
