"""v5.11.21 regression tests — REQ-DEDUPE-1 / REQ-LADDER-WALK /
REQ-PROVIDER-HEALTH-TEXT / REQ-PUBLISH-HONESTY / REQ-REAPER-1.

These are source-level and pure-logic tests (no DB, no network) in the same
style as test_v595_sla_governor.py: they pin the SEMANTICS that the incident
of 2026-07-24 proved matter, so a future refactor cannot silently regress
them without a red test naming the ledger entry.
"""
import inspect
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------- REQ-DEDUPE-1
def test_once_keys_skip_status_filter():
    """once~ keys must dedupe in ANY status; plain keys stay pending-only."""
    src = _src("agentcore/jobs.py")
    body = src.split("def _find_by_idempotency", 1)[1]
    assert 'startswith("once~")' in body, "once~ namespace check missing"
    # The status filter must be applied only on the non-once~ branch.
    assert re.search(r'if not key\.startswith\("once~"\):\s*\n\s*q = q\.in_', body), \
        "status filter must be conditional on the key NOT being once~"


def test_calendar_spawns_use_once_namespace():
    src = _src("workers/departments/portfolio.py")
    assert 'once~mix:' in src
    assert 'once~ideate:' in src
    assert 'once~carousel:' in src


def test_selfscheduling_chains_stay_plain():
    """tick/replan (portfolio) and hb (ops) must NOT be once~ — pending-only
    semantics is what lets chains re-enqueue after completion (v5.6.1)."""
    pf = _src("workers/departments/portfolio.py")
    ops = _src("workers/departments/ops.py")
    assert 'f"tick:' in pf and 'once~tick' not in pf
    assert 'f"replan:' in pf and 'once~replan' not in pf
    assert 'f"hb:' in ops and 'once~hb' not in ops


def test_plan_handlers_have_claim_time_governor():
    src = _src("workers/departments/editorial.py")
    for fn in ("plan_carousel", "plan_story"):
        body = src.split(f"def {fn}", 1)[1].split("\ndef ", 1)[0]
        assert "produced_by_format_today" in body, f"{fn}: governor missing"
        assert '"quota_met"' in body, f"{fn}: quota no-op missing"
        assert "_topic_exists_today" in body, f"{fn}: same-topic guard missing"


def test_topic_guard_ignores_terminal_negatives():
    """rejected/cleared/failed must NOT block a fresh take on the topic."""
    src = _src("workers/departments/editorial.py")
    body = src.split("def _topic_exists_today", 1)[1].split("\ndef ", 1)[0]
    for st in ("idea", "drafted", "approved", "scheduled", "published"):
        assert f'"{st}"' in body
    for st in ("rejected", "cleared", "failed"):
        assert f'"{st}"' not in body


# ------------------------------------------------------------ REQ-LADDER-WALK
def test_debate_walks_full_ladder():
    src = _src("agentcore/council.py")
    body = src.split("def debate", 1)[1].split("\ndef ", 1)[0]
    assert "for prov, model in provs[:2]" not in body, \
        "debate must not truncate the ladder"
    assert "_walk_ladder" in body
    walk = src.split("def _walk_ladder", 1)[1].split("\ndef ", 1)[0]
    assert "for prov, model in provs" in walk
    assert "want" in walk


def test_groq_is_first_free_rung():
    src = _src("agentcore/council.py")
    groq = src.index('("groq",')
    gemini = src.index('("gemini",')
    assert groq < gemini, "REQ-LADDER-ORDER: groq must precede gemini"


# --------------------------------------------------- REQ-PROVIDER-HEALTH-TEXT
def test_llm_call_reports_provider_health():
    src = _src("agent/llm.py")
    assert "urllib.error" in src.split("\n")[7] or "import urllib.error" in src \
        or "urllib.request, urllib.error" in src
    body = src.split("def _call(", 1)[1].split("def _call_raw", 1)[0]
    assert "mark_ok" in body and "mark_error" in body
    assert "HTTPError" in body
    # message must carry provider/model/status for operators + council matching
    assert "HTTP {e.code}" in body


# ------------------------------------------------------- REQ-PUBLISH-HONESTY
def test_publish_never_lies_about_dry_runs():
    src = _src("workers/departments/distribution.py")
    body = src.split("def publish", 1)[1].split("\ndef ", 1)[0]
    # live/dry must be computed BEFORE the status update
    assert body.index("published_live = bool(live)") < body.index('"status": "published"')
    assert '"dry_run_only": True' in body
    assert "publish_dry_run" in body
    # Priority is actually imported now (was a swallowed NameError)
    header = src.split("def ", 1)[0]
    assert re.search(r"from agentcore import .*Priority", header)


# --------------------------------------------------------------- REQ-REAPER-1
def test_reaper_semantics():
    src = _src("workers/departments/ops.py")
    body = src.split("def _reap_stale_jobs", 1)[1].split("\ndef ", 1)[0]
    assert '"claimed", "in_progress"' in body
    # CAS on status so a completing job is never clobbered
    assert body.count('.in_("status", ["claimed", "in_progress"])') >= 1
    assert '"status": "queued"' in body and '"status": "failed"' in body
    hb = src.split("def heartbeat", 1)[1].split("\ndef ", 1)[0]
    assert "_reap_stale_jobs" in hb, "reaper must be wired into the heartbeat"
    assert 'STALE_JOB_MIN = int(os.environ.get("STALE_JOB_MIN", "90"))' in src
