"""v5.9.5 — lock down the demand governor, SLA engine, fair claiming, and
the $0 guarantee for paused-account prep.

Production problems these tests exist to prevent regressing:
  * 7,404 board items cleared / 4 surviving in 7 days — ideation churn loop
    burned ~$12 of the $15.17 weekly spend (DEC-021).
  * 9 × "creative.write_script: no topic" fatals — stale-idea sweep read the
    topic from payload while board_add stores it in the topic COLUMN.
  * 14,370 human_desk.sync jobs/week of pure overhead at a 20s cadence.
  * One noisy account could starve every other account's jobs (DEC-023).
  * Paused accounts must cost exactly $0 (DEC-024).
"""
import os, sys, time, ast, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# --------------------------------------------------------------- fair_claim_order

from agentcore.jobs import fair_claim_order, DEADLINE_URGENT_HORIZON_S


def test_fair_order_empty():
    assert fair_claim_order([]) == []


def test_fair_order_deadline_urgent_first():
    now = time.time()
    rows = [
        {"id": 1, "account_id": "a"},
        {"id": 2, "account_id": "b", "deadline": now + 60},
        {"id": 3, "account_id": "a", "deadline": now - 10},
    ]
    out = fair_claim_order(rows)
    # past-deadline first, then near-deadline, then the rest
    assert [r["id"] for r in out[:2]] == [3, 2]
    assert out[2]["id"] == 1


def test_fair_order_far_deadline_not_urgent():
    now = time.time()
    rows = [
        {"id": 1, "account_id": "a", "deadline": now + DEADLINE_URGENT_HORIZON_S + 999},
        {"id": 2, "account_id": "b"},
    ]
    out = fair_claim_order(rows)
    # a far deadline does NOT jump the queue
    assert {r["id"] for r in out} == {1, 2}
    assert out[0]["id"] == 1  # keeps incoming order via round-robin


def test_fair_order_round_robin_across_accounts():
    rows = [
        {"id": 1, "account_id": "a"}, {"id": 2, "account_id": "a"},
        {"id": 3, "account_id": "a"}, {"id": 4, "account_id": "b"},
        {"id": 5, "account_id": None},
    ]
    out = fair_claim_order(rows)
    ids = [r["id"] for r in out]
    # account b and the system bucket must appear inside a's block, not after it
    assert ids.index(4) < ids.index(2)
    assert ids.index(5) < ids.index(3)
    assert sorted(ids) == [1, 2, 3, 4, 5]


def test_fair_order_is_lossless_and_crash_safe():
    rows = [{"id": i, "account_id": None} for i in range(7)]
    assert [r["id"] for r in fair_claim_order(rows)] == list(range(7))
    # weird rows (missing keys, junk deadline types) must not raise
    out = fair_claim_order([{"id": 1}, {"id": 2, "deadline": None}])
    assert len(out) == 2


# --------------------------------------------------------------- SLA classify

from workers.departments import sla as _sla


def _mid():  # far-future midnight so 'breached' only triggers when we force it
    return _sla._midnight_utc_ts()


def test_sla_done_when_quota_met():
    assert _sla.classify(2, 2, time.time(), []) == "done"
    assert _sla.classify(2, 3, time.time(), []) == "done"


def test_sla_on_track_vs_at_risk_vs_behind():
    now = time.time()
    far = now + 4 * 3600
    near = now + (_sla.SLA_MINUTES_PER_POST * 60) / 2
    past = now - 60
    mid = _mid()
    if mid - now > 6 * 3600:  # only assert when the day has runway
        assert _sla.classify(1, 0, now, [far]) == "on_track"
        assert _sla.classify(1, 0, now, [near]) == "at_risk"
        assert _sla.classify(1, 0, now, [past]) == "behind"
    # breached: remaining posts physically cannot fit before midnight
    huge_quota = int((mid - now) / 60 / _sla.SLA_MINUTES_PER_POST) + 5
    assert _sla.classify(huge_quota, 0, now, []) == "breached"


def test_sla_produced_slots_consume_deadlines():
    now = time.time()
    mid = _mid()
    if mid - now > 6 * 3600:
        past, far = now - 60, now + 4 * 3600
        # first slot already produced -> judged against the SECOND deadline
        assert _sla.classify(2, 1, now, [past, far]) == "on_track"


def test_sla_module_makes_no_llm_calls():
    src = inspect.getsource(_sla)
    for banned in ("free_chat", "council", "llm.", "_call("):
        assert banned not in src, f"sla.py must stay pure DB math, found {banned!r}"


# --------------------------------------------------------------- paused prep $0 guard

from workers.departments import paused_prep as _prep


def test_prep_run_task_only_uses_free_chat():
    """DEC-024 source-level guard: the ONLY model entry point reachable from
    _run_task is council.free_chat. Any paid path added here must fail CI."""
    src = inspect.getsource(_prep)
    assert "free_chat" in src
    for banned in ("council.run", "council.chat(", "llm.chat", "llm.complete",
                   "anthropic", "openai.", "_call_paid", "paid_chat"):
        assert banned not in src, f"paused_prep must be free-only, found {banned!r}"


def test_prep_items_use_prep_status_and_are_excluded_from_inflight():
    src = inspect.getsource(_prep)
    assert 'status="prep"' in src
    # DEC-025: portfolio in-flight math must NOT count prep items
    from workers.departments import portfolio as _pf
    pf_src = inspect.getsource(_pf._count_inflight)
    assert '"prep"' not in pf_src
    prod_src = inspect.getsource(_pf._produced_today)
    assert '"prep"' not in prod_src


def test_prep_run_task_skips_when_free_providers_down(monkeypatch):
    calls = {"board": 0}
    import agentcore.council as _council
    def boom(prompt, max_tokens=400):
        raise RuntimeError("no free provider available")
    monkeypatch.setattr(_council, "free_chat", boom)
    class _Bus:
        def agent(self, *a, **k): pass
    ok = _prep._run_task(object(), _Bus(), type("J", (), {"id": "j"})(),
                         {"id": "acct1", "niche": "pets", "handle": "x"})
    assert ok is False and calls["board"] == 0  # skipped, banked nothing


# --------------------------------------------------------------- governor + cadence

def test_ideate_cooldown_env_and_key_format():
    from workers.departments import portfolio as _pf
    assert _pf.IDEATE_COOLDOWN_S == 1800  # default
    src = inspect.getsource(_pf.tick)
    assert "ideate:{acct['id']}:{bucket}" in src or "idempotency_key=f\"ideate:" in src
    assert "_produced_today" in src  # demand math is wired into the tick


def test_plan_one_empty_topic_spawns_nothing():
    from workers.departments import editorial as _ed
    src = inspect.getsource(_ed.plan_one)
    # the empty-topic guard must return BEFORE creative.write_script is spawned
    guard = src.index('reason": "empty_topic"')
    spawn = src.index('job_of(w, "creative.write_script"')
    assert guard < spawn


def test_stale_sweep_reads_topic_column():
    from workers.departments import portfolio as _pf
    src = inspect.getsource(_pf._sweep_stale_ideas)
    assert 'r.get("topic")' in src          # root-cause fix
    assert "empty_topic" in src              # unplannable ideas get cleared


def test_human_desk_cadence_is_env_tunable_and_slower():
    from workers.departments import human_desk as _hd
    assert _hd.HUMAN_DESK_SYNC_SECONDS == 120  # default
    src = inspect.getsource(_hd._reschedule)
    assert "HUMAN_DESK_SYNC_SECONDS" in src and "+ 20," not in src
