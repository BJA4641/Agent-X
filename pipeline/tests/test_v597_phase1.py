"""v5.9.7 — Phase 1 "Prove the Loop": stage deadlines, opt-in auto-approve,
cost-per-published-post.

Why each exists:
  * REQ-SLASTAGE-1 — a single end-of-day deadline is unactionable; by the time
    it breaches it is too late. Per-stage deadlines feed fair_claim_order, which
    already pulls deadline-urgent jobs first, so stamping them converts the
    v5.9.5 fairness mechanism into real SLA enforcement.
  * REQ-AUTOAPPROVE-1 — the founder sits in EVERY publish path today. That is
    the throughput ceiling for Phase 1. Removing a human from publishing is a
    safety decision, so the gate is OFF by default and strict when on (DEC-038).
  * REQ-COSTPOST-1 — v5.9.5 cut spend 83% while producing nothing, which reads
    as success on every cost metric the platform had. Cost per PUBLISHED post is
    the denominator that makes cost control honest.
"""
import os, sys, time, inspect, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from workers.departments import sla as _sla
from workers.departments import cqo as _cqo


# ------------------------------------------------- REQ-SLASTAGE-1

def test_stage_deadline_is_earlier_for_earlier_stages():
    publish = time.time() + 6 * 3600
    d_write = _sla.stage_deadline("creative.write_script", publish)
    d_grade = _sla.stage_deadline("cqo.grade_script", publish)
    d_render = _sla.stage_deadline("creative.render", publish)
    d_pub = _sla.stage_deadline("distribution.publish", publish)
    assert d_write < d_grade < d_render < d_pub <= publish


def test_stage_deadline_subtracts_downstream_budgets():
    publish = 1_000_000.0
    # everything after write_script: grade 15 + render 30 + finish 15 + inject 5 + publish 10 = 75 min
    assert _sla.stage_deadline("creative.write_script", publish) == publish - 75 * 60


def test_last_stage_equals_publish_deadline():
    publish = 1_000_000.0
    assert _sla.stage_deadline("distribution.publish", publish) == publish


def test_unknown_stage_is_loose_not_wrong():
    publish = 1_000_000.0
    assert _sla.stage_deadline("ops.heartbeat", publish) == publish
    assert _sla.stage_deadline("", publish) == publish


def test_every_ordered_stage_has_a_budget():
    for t in _sla.STAGE_ORDER:
        assert t in _sla.STAGE_BUDGETS_MIN, f"{t} is ordered but has no time budget"


def test_full_chain_fits_inside_a_working_day():
    total = sum(_sla.STAGE_BUDGETS_MIN[t] for t in _sla.STAGE_ORDER)
    assert total <= 8 * 60, "a full pipeline must fit inside the production window"


def test_monitor_stamps_stage_deadlines():
    src = inspect.getsource(_sla.monitor)
    assert "stage_deadline" in src and 'is_("deadline", "null")' in src


# ------------------------------------------------- REQ-AUTOAPPROVE-1

from workers.departments.cqo import auto_approve_decision, AUTO_APPROVE_DEFAULT_MIN


def _aa(**kw):
    d = dict(enabled=True, overall=9.0, min_score=8.5,
             dimension_scores={"hook": 9, "visuals": 9, "pacing": 8.5},
             min_dim=6.0, risk_flags=None)
    d.update(kw)
    return d


def test_auto_approve_is_off_by_default():
    """Autonomous publishing must never be the default (DEC-038)."""
    ok, why = auto_approve_decision(**_aa(enabled=False))
    assert ok is False and "disabled" in why


def test_auto_approve_bar_is_stricter_than_ship_floor():
    assert AUTO_APPROVE_DEFAULT_MIN > _cqo.SHIP_FLOOR


def test_auto_approve_allows_a_strong_draft():
    ok, why = auto_approve_decision(**_aa())
    assert ok is True and "9.0" in why


def test_auto_approve_rejects_below_bar():
    ok, why = auto_approve_decision(**_aa(overall=8.0))
    assert ok is False and "below auto-approve bar" in why


def test_auto_approve_rejects_weak_dimension():
    ok, why = auto_approve_decision(**_aa(dimension_scores={"hook": 9.5, "cta": 3.0}))
    assert ok is False and "weakest dimension" in why


def test_risk_flags_always_force_human_review():
    ok, why = auto_approve_decision(**_aa(overall=10.0, risk_flags=["health_claim"]))
    assert ok is False and "risk flags" in why


def test_auto_approve_config_defaults_to_off_on_error():
    enabled, min_score = _cqo._auto_approve_config(None)
    assert enabled is False and min_score == AUTO_APPROVE_DEFAULT_MIN


def test_human_gate_kept_when_auto_approve_errors():
    src = inspect.getsource(_cqo.grade_script)
    assert "_maybe_auto_approve" in src
    assert "human gate kept" in src, "an error in the gate must fail CLOSED"


def test_auto_approve_happens_before_render_chain():
    src = inspect.getsource(_cqo.grade_script)
    assert src.index("_maybe_auto_approve") < src.index('job_of(w, "creative.render"')


# ------------------------------------------------- REQ-COSTPOST-1

def test_cost_per_post_writer_exists_and_handles_zero_posts():
    assert callable(_sla._write_cost_per_post)
    src = inspect.getsource(_sla._write_cost_per_post)
    assert "cost_per_post_today" in src and "cost_per_post_all_time" in src
    # division by zero must yield None, not a crash or a fake 0
    assert "if pub_today else None" in src
    assert "if pub_all else None" in src


def test_cost_per_post_is_written_every_monitor_pass():
    src = inspect.getsource(_sla.monitor)
    assert "_write_cost_per_post" in src


def test_cost_per_post_counts_published_only():
    """Cleared/rejected items must never flatter the denominator."""
    src = inspect.getsource(_sla._write_cost_per_post)
    assert '"published"' in src
    for bad in ('"cleared"', '"approved"', '"drafted"'):
        assert bad not in src


# ------------------------------------------------- release integrity

def test_version_bumped():
    import workers.runner as r
    assert r.VERSION == "5.9.7"


def test_prior_guarantees_still_hold():
    """Batch 1 invariants must survive Batch 2."""
    from agentcore.council import merge_ladder, _FREE_ORDER
    assert len(merge_ladder([("gemini", "x")])) >= len(_FREE_ORDER)
    from workers.departments.creative import escalation_allowed
    assert escalation_allowed(
        kill_switch_on=True, free_only=False, daily_remaining=9.0,
        account_month_remaining=9.0, est_cost=0.02, sla_state="breached",
        produced_today=0, enabled=True)[0] is False
    from workers.departments import paused_prep as pp
    assert "free_chat" in inspect.getsource(pp)
