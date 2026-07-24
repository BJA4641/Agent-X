"""preflight.py — v5.10.9 REQ-UPLOAD-GUARD.

Why this exists
---------------
Releases reach production as zips uploaded through the GitHub web UI, one file
at a time. On 2026-07-24 the v5.10.7 zip landed *except* for
workers/departments/portfolio.py. The test suite caught it — correctly — but
reported it as three unrelated failures:

    FAILED test_backpressure_pauses_production_when_drafts_pile_up
    FAILED test_awaiting_approval_counts_only_drafted
    FAILED test_awaiting_approval_fails_safe_to_zero

Nothing in that output says "you missed a file". This script does.

It checks that every symbol a shipped release depends on actually exists in the
deployed tree, and when one is missing it names the file, the release, and what
to re-upload. Runs in well under a second, before pytest, with no dependencies.

Adding to this list is part of shipping a release: if a batch introduces a new
public symbol, add it here so a partial upload fails loudly on the right line.
"""
from __future__ import annotations
import importlib
import os
import sys

# (module path, symbol, release that introduced it, file to re-upload)
REQUIRED = [
    # v5.9.5 — demand governor, SLA engine, $0 paused prep
    ("workers.departments.portfolio", "IDEATE_COOLDOWN_S", "v5.9.5", "pipeline/workers/departments/portfolio.py"),
    ("workers.departments.sla", "classify", "v5.9.5", "pipeline/workers/departments/sla.py"),
    ("workers.departments.paused_prep", "prep_cycle", "v5.9.5", "pipeline/workers/departments/paused_prep.py"),
    ("agentcore.jobs", "fair_claim_order", "v5.9.5", "pipeline/agentcore/jobs.py"),
    # v5.9.6 — ladder floor + paid escalation
    ("agentcore.council", "merge_ladder", "v5.9.6", "pipeline/agentcore/council.py"),
    ("workers.departments.creative", "escalation_allowed", "v5.9.6", "pipeline/workers/departments/creative.py"),
    ("workers.departments.portfolio", "INFLIGHT_MAX_AGE_H", "v5.9.6", "pipeline/workers/departments/portfolio.py"),
    ("workers.departments.ops", "start_heartbeat_pulse", "v5.9.6", "pipeline/workers/departments/ops.py"),
    # v5.9.7 — stage deadlines, auto-approve, cost per post
    ("workers.departments.sla", "stage_deadline", "v5.9.7", "pipeline/workers/departments/sla.py"),
    ("workers.departments.cqo", "auto_approve_decision", "v5.9.7", "pipeline/workers/departments/cqo.py"),
    ("workers.departments.sla", "_write_cost_per_post", "v5.9.7", "pipeline/workers/departments/sla.py"),
    # v5.9.8 — single source of truth for version
    ("agentcore.version", "VERSION", "v5.9.8", "pipeline/agentcore/version.py + web/version.json"),
    # v5.10.0 — art director
    ("workers.departments.art_director", "compose_prompt", "v5.10.0", "pipeline/workers/departments/art_director.py"),
    # v5.10.1 — rate limiting
    ("agentcore.ratelimit", "acquire", "v5.10.1", "pipeline/agentcore/ratelimit.py"),
    # v5.10.2 — concurrency + lanes + backoff release
    ("agentcore.worker", "lane_for", "v5.10.2", "pipeline/agentcore/worker.py"),
    ("workers.departments.sla", "ladder_is_healthy", "v5.10.2", "pipeline/workers/departments/sla.py"),
    # v5.10.4 — spend stampede guard
    ("workers.departments.creative", "escalations_last_hour", "v5.10.4", "pipeline/workers/departments/creative.py"),
    # v5.10.7 — backpressure  (THIS is the one that silently failed to upload)
    ("workers.departments.portfolio", "awaiting_approval", "v5.10.7", "pipeline/workers/departments/portfolio.py"),
    ("workers.departments.portfolio", "MAX_AWAITING_APPROVAL", "v5.10.7", "pipeline/workers/departments/portfolio.py"),
    # v5.11.21 — dedupe namespace, full-ladder council, honest publish, reaper
    ("agentcore.council", "_walk_ladder", "v5.11.21", "pipeline/agentcore/council.py"),
    ("agent.llm", "_call_raw", "v5.11.21", "pipeline/agent/llm.py"),
    ("workers.departments.editorial", "_topic_exists_today", "v5.11.21", "pipeline/workers/departments/editorial.py"),
    ("workers.departments.ops", "_reap_stale_jobs", "v5.11.21", "pipeline/workers/departments/ops.py"),
    ("workers.departments.ops", "STALE_JOB_MIN", "v5.11.21", "pipeline/workers/departments/ops.py"),
    # v5.11.22 — topic memory, content-derived carousel titles, photo-real slides
    ("workers.departments.editorial", "_topics_recent", "v5.11.22", "pipeline/workers/departments/editorial.py"),
    ("agent.visuals", "REALISTIC_STYLES", "v5.11.22", "pipeline/agent/visuals.py"),
    # v5.11.23 — lessons loop: rejection reasons feed the writers
    ("workers.common", "lessons_for", "v5.11.23", "pipeline/workers/common.py"),
    # v5.11.24 — workbook system: per-agent playbooks + per-account manual
    ("agentcore.playbooks", "get_playbook", "v5.11.24", "pipeline/agentcore/playbooks.py"),
]


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    missing = []
    for mod_path, symbol, release, upload in REQUIRED:
        try:
            mod = importlib.import_module(mod_path)
        except Exception as e:
            missing.append((mod_path, symbol, release, upload, f"module import failed: {e}"))
            continue
        if not hasattr(mod, symbol):
            missing.append((mod_path, symbol, release, upload, "symbol not found"))

    if not missing:
        print(f"PREFLIGHT OK — all {len(REQUIRED)} release symbols present.")
        return 0

    print("=" * 72)
    print("PREFLIGHT FAILED — a file from a shipped release is missing or stale.")
    print("This is almost always a PARTIAL UPLOAD, not a code bug.")
    print("=" * 72)
    stale_files = sorted({m[3] for m in missing})
    for mod_path, symbol, release, upload, why in missing:
        print(f"  {release}  {mod_path}.{symbol}  -> {why}")
    print("-" * 72)
    print("RE-UPLOAD THESE FILES (from the release zip of the same version):")
    for f in stale_files:
        print(f"  * {f}")
    print("=" * 72)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
