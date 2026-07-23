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

try:
    from agentcore.version import VERSION           # v5.9.8 REQ-VERSION-1: one source
except Exception:                                    # pragma: no cover
    VERSION = "5.9.8"
# History: 5.9.8 single-source version + missing dashboard pages + repo hygiene | 5.9.7 stage deadlines, opt-in auto-approve, cost-per-post | 5.9.6 ladder floor + paid escalation | 5.9.5 demand governor, SLA engine


INVENTORY_KEYS = [
    # LLM / text
    "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
    "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "XAI_API_KEY",
    "TOGETHER_API_KEY", "FIREWORKS_API_KEY", "COHERE_API_KEY",
    # image / video
    "FAL_KEY", "REPLICATE_API_TOKEN", "STABILITY_API_KEY", "BFL_API_KEY",
    "IDEOGRAM_API_KEY", "RECRAFT_API_KEY", "GOAPI_KEY",
    # voice / audio
    "ELEVENLABS_API_KEY", "CARTESIA_API_KEY", "PLAYHT_API_KEY", "DEEPGRAM_API_KEY",
    # publishing
    "IG_ACCESS_TOKEN", "IG_USER_ID", "YT_API_KEY", "YOUTUBE_API_KEY", "YT_TOKEN_JSON",
    "TIKTOK_ACCESS_TOKEN", "X_API_KEY", "LINKEDIN_ACCESS_TOKEN",
]

def _write_provider_inventory(rt, version: str):
    """v5.8.5: publish which API keys the WORKER process actually has (presence
    only, never values) so the dashboard can show ground truth instead of
    guessing from Vercel's separate environment."""
    try:
        sb = rt.deps.get("supabase") and rt.deps["supabase"]()
        if sb is None:
            return
        tenant = os.environ.get("TENANT_ID", "me")
        # v5.8.7: alias-aware. Several capabilities accept more than one env
        # spelling (voice.py already reads ELEVEN_API_KEY *or* ELEVENLABS_API_KEY).
        # Reporting the alias as "missing" made the dashboard lie.
        ALIASES = {
            "ELEVENLABS_API_KEY": ["ELEVEN_API_KEY"],
            "YOUTUBE_API_KEY":    ["YT_API_KEY"],
            "YT_API_KEY":         ["YOUTUBE_API_KEY"],
            "FAL_KEY":            ["FAL_API_KEY"],
            "GEMINI_API_KEY":     ["GOOGLE_API_KEY"],
        }
        def _present(k):
            if os.environ.get(k):
                return True
            return any(os.environ.get(a) for a in ALIASES.get(k, []))
        keys = {k: _present(k) for k in INVENTORY_KEYS}
        # v5.9.0: publish the EFFECTIVE runtime config too. hard_budget_ok()
        # reads DAILY_BUDGET_USD from the worker env, NOT from settings.daily_budget
        # — so the dashboard could show $2.50 while the worker enforced $1.00 and
        # refused every tick with no visible reason. Now the real number is on record.
        try:
            from agentcore import config as _c
            effective = {"daily_budget_usd": _c.DAILY_BUDGET_USD,
                         "tenant_id": _c.TENANT_ID,
                         "env_daily_budget_raw": os.environ.get("DAILY_BUDGET_USD")}
        except Exception as _e:
            effective = {"error": str(_e)[:120]}
        sb.table("settings").upsert({
            "tenant_id": tenant, "key": "provider_inventory",
            "value": {"checked_at": time.time(), "worker_version": version,
                      "effective_config": effective,
                      "keys": keys,
                      "present": sorted([k for k, v in keys.items() if v]),
                      "missing": sorted([k for k, v in keys.items() if not v])},
        }, on_conflict="tenant_id,key").execute()
        print(f"  provider inventory: {sum(keys.values())}/{len(keys)} keys present -> settings.provider_inventory")
    except Exception as e:
        print(f"  provider inventory failed (non-fatal): {e}")


def main():
    rt = get_runtime()
    _write_provider_inventory(rt, VERSION)
    # v5.9.3: an ops.heartbeat job left in_progress by a killed container broke
    # the heartbeat chain FOREVER (each heartbeat enqueues the next one), so the
    # dashboard reported "worker is not beating" about a perfectly healthy
    # worker. Reap orphans at boot.
    try:
        sb0 = rt.deps.get("supabase") and rt.deps["supabase"]()
        if sb0 is not None:
            sb0.table("jobs").update({"status": "queued", "claimed_at": None}) \
               .eq("status", "in_progress").lt("scheduled_for", time.time() - 300).execute()
            print("  reaped orphaned in_progress jobs")
    except Exception as e:
        print(f"  orphan reap skipped: {e}")

    worker = Worker(rt.queue, name="agentx-v5", poll_interval=2.5)
    worker.set_deps(**rt.deps)
    register_all(worker)

    # v5.9.6 REQ-HEALTH-1: authoritative liveness from a daemon thread, so a
    # slow job can no longer make a healthy worker look dead on the dashboard.
    try:
        from workers.departments.ops import start_heartbeat_pulse
        start_heartbeat_pulse(rt.deps.get("supabase"), worker.id, VERSION, time.time())
        print("  heartbeat pulse thread started")
    except Exception as e:
        print(f"  heartbeat pulse not started (non-fatal): {e}")

    # ---- Bootstrap self-scheduling jobs (idempotent keys prevent dupes after restart) ----
    now = time.time()
    boot_jobs = [
        Job(job_type="strategy.arena_scout", payload={"boot": True},
            priority=Priority.LOW, scheduled_for=now + 90,
            idempotency_key=f"arena:boot:{int(now)}"),
        Job(job_type="strategy.audit", payload={"boot": True},
            priority=Priority.LOW, scheduled_for=now + 150,
            idempotency_key=f"audit:boot:{int(now)}"),
        Job(job_type="providers.probe", payload={"boot": True},
            priority=Priority.HIGH, scheduled_for=now + 20,
            idempotency_key=f"probe:boot:{int(now)}"),
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
            idempotency_key=f"desksync:{int(now//120)}"),
        # v5.9.5 — seed the SLA + paused-prep self-scheduling chains.
        # Idempotency keys make reboots safe: an existing chain absorbs these.
        Job(job_type="sla.plan_day", payload={"boot": True},
            priority=Priority.LOW, scheduled_for=now + 45,
            idempotency_key=f"slaplan:{time.strftime('%Y-%m-%d', time.gmtime(now))}"),
        Job(job_type="sla.monitor", payload={"boot": True},
            priority=Priority.LOW, scheduled_for=now + 120,
            idempotency_key=f"slamon:{int((now + 120)//300)}"),
        Job(job_type="paused.prep_cycle", payload={"boot": True},
            priority=Priority.LOW, scheduled_for=now + 300,
            idempotency_key=f"prep:{int((now + 300)//3600)}"),
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
