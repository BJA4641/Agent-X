"""v5.9.6 — guard the fixes that ended the all-time zero-output record.

Production failures these lock down:
  * council._order() REPLACED the hardcoded 5-rung free ladder with whatever
    strategy.arena_scout wrote. A 2-rung ladder + gemini 429 + expired groq key
    = zero free capacity = writer delayed 30 min forever with a full wallet.
    ZERO items published in the platform's entire history (REQ-LADDER-FLOOR).
  * The writer had no rung ABOVE free: escalation to paid never existed
    (REQ-ESCALATE-1).
  * Stalled board items counted as "in flight" forever, so the demand governor
    computed need=-1 and suppressed ideation while output was zero (REQ-GOV-2).
  * The re-plan path had no idempotency key — one topic queued 5x (REQ-DEDUPE-1).
  * Job errors were truncated to 150 chars, cutting the provider list mid-word
    and destroying the evidence needed to diagnose all of the above (REQ-DIAG-1).
  * SLA measured an 08:00-22:00 UTC window instead of 14:00 Asia/Dubai (REQ-SLA-TZ).
"""
import os, sys, time, inspect, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


# ------------------------------------------------- REQ-LADDER-FLOOR

from agentcore.council import merge_ladder, LADDER_FLOOR_MIN, _FREE_ORDER


def test_ladder_floor_survives_a_narrow_arena_write():
    """THE regression test. arena_scout wrote a 2-rung ladder; the 3 openrouter
    fallbacks vanished; free capacity hit zero. Never again."""
    arena_narrow = [("gemini", "gemini-2.5-flash"), ("groq", "llama-3.3-70b-versatile")]
    out = merge_ladder(arena_narrow)
    assert len(out) >= LADDER_FLOOR_MIN
    assert len(out) >= len(_FREE_ORDER), "hardcoded floor must never be lost"
    assert any(p == "openrouter" for p, _ in out), "openrouter fallbacks must survive"


def test_ladder_puts_arena_picks_first():
    arena = [("openrouter", "brand/new-model:free")]
    out = merge_ladder(arena)
    assert out[0] == ("openrouter", "brand/new-model:free")


def test_ladder_dedupes_without_losing_order():
    arena = [("gemini", "gemini-2.5-flash")]
    out = merge_ladder(arena)
    assert out.count(("gemini", "gemini-2.5-flash")) == 1


def test_ladder_empty_arena_falls_back_to_floor():
    assert merge_ladder([]) == [(p, m) for p, m in _FREE_ORDER]
    assert merge_ladder(None) == [(p, m) for p, m in _FREE_ORDER]


def test_ladder_ignores_malformed_entries():
    out = merge_ladder([("gemini",), None, ("", "x"), ("groq", None), ("ok", "model")])
    assert ("ok", "model") in out
    assert len(out) >= len(_FREE_ORDER)


def test_order_merges_not_replaces_in_source():
    import agentcore.council as c
    src = inspect.getsource(c._order)
    assert "merge_ladder" in src
    assert "return picked" not in src, "_order must never return arena picks alone"


# ------------------------------------------------- REQ-ESCALATE-1

from workers.departments.creative import escalation_allowed


def _base(**kw):
    d = dict(kill_switch_on=False, free_only=False, daily_remaining=5.0,
             account_month_remaining=20.0, est_cost=0.02, sla_state="on_track",
             produced_today=1, enabled=True)
    d.update(kw)
    return d


def test_escalation_blocked_by_every_guard():
    assert escalation_allowed(**_base(kill_switch_on=True))[0] is False
    assert escalation_allowed(**_base(free_only=True))[0] is False
    assert escalation_allowed(**_base(daily_remaining=0.001))[0] is False
    assert escalation_allowed(**_base(account_month_remaining=0.0))[0] is False
    assert escalation_allowed(**_base(enabled=False))[0] is False


def test_escalation_allowed_on_deadline_pressure():
    for state in ("at_risk", "behind", "breached"):
        ok, why = escalation_allowed(**_base(sla_state=state))
        assert ok is True and state in why


def test_escalation_allowed_when_nothing_published_today():
    ok, why = escalation_allowed(**_base(produced_today=0))
    assert ok is True and "first post" in why


def test_escalation_declined_when_healthy_and_progressing():
    ok, why = escalation_allowed(**_base(produced_today=2, sla_state="on_track"))
    assert ok is False and "no deadline pressure" in why


def test_guards_outrank_justifications():
    """A breached SLA must NOT punch through the kill switch or the $25 cap."""
    assert escalation_allowed(**_base(sla_state="breached", kill_switch_on=True))[0] is False
    assert escalation_allowed(**_base(sla_state="breached", account_month_remaining=0.0))[0] is False
    assert escalation_allowed(**_base(produced_today=0, free_only=True))[0] is False


def test_delay_is_now_the_last_resort_in_source():
    import workers.departments.creative as cr
    src = inspect.getsource(cr.write_script)
    esc = src.index("_escalate_to_paid")
    delay = src.index("scheduled_for\": time.time() + 1800")
    assert esc < delay, "escalation must be attempted BEFORE the 30-minute delay"


# ------------------------------------------------- REQ-DIAG-1

def test_error_truncation_widened():
    import workers.departments.creative as cr
    src = inspect.getsource(cr.write_script)
    assert "str(e)[:900]" in src
    assert "no model: {str(e)[:150]}" not in src, "150-char truncation destroyed the evidence"


def test_free_chat_reports_unattempted_rungs():
    import agentcore.council as c
    src = inspect.getsource(c.free_chat)
    assert "NOT ATTEMPTED" in src and "usable_rungs" in src


def test_ladder_report_shape():
    import agentcore.council as c
    assert callable(c.ladder_report)
    src = inspect.getsource(c.ladder_report)
    for field in ("usable", "dropped", "below_floor"):
        assert field in src


# ------------------------------------------------- REQ-GOV-2 / REQ-DEDUPE-1

def test_inflight_ages_out_stalled_items():
    from workers.departments import portfolio as pf
    assert pf.INFLIGHT_MAX_AGE_H == 6
    assert pf.INFLIGHT_MAX_AGE_H > pf.STALE_IDEA_HOURS, \
        "sweep must get first attempt before the governor stops counting the item"
    src = inspect.getsource(pf._count_inflight)
    assert "INFLIGHT_MAX_AGE_H" in src and "gte(\"created_at\"" in src


def test_replan_spawn_is_idempotent():
    from workers.departments import portfolio as pf
    src = inspect.getsource(pf._sweep_stale_ideas)
    assert 'idempotency_key=f"replan:{r[\'id\']}"' in src


# ------------------------------------------------- REQ-SLA-TZ

from workers.departments import sla as _sla


def test_deadline_resolves_to_1400_dubai():
    day = dt.date(2026, 7, 24)
    ts = _sla.resolve_deadline_utc("14:00", "Asia/Dubai", day)
    utc = dt.datetime.utcfromtimestamp(ts)
    assert (utc.hour, utc.minute) == (10, 0), "14:00 Dubai == 10:00 UTC"
    assert utc.date() == day


def test_deadline_defaults_match_founder_mandate():
    assert _sla.SLA_DEADLINE_LOCAL == "14:00"
    assert _sla.SLA_TIMEZONE == "Asia/Dubai"


def test_per_account_deadline_override():
    day = dt.date(2026, 7, 24)
    acct = {"config": {"sla_deadline": "09:30", "sla_timezone": "Europe/London"}}
    ts = _sla.account_deadline_utc(acct, day)
    utc = dt.datetime.utcfromtimestamp(ts)
    assert (utc.hour, utc.minute) == (8, 30), "09:30 London == 08:30 UTC in July (BST)"


def test_account_without_override_uses_default():
    day = dt.date(2026, 7, 24)
    assert _sla.account_deadline_utc({}, day) == _sla.resolve_deadline_utc(day=day)


# ------------------------------------------------- REQ-PREPOBS-1

def test_prep_skip_is_never_silent():
    from workers.departments import paused_prep as pp
    src = inspect.getsource(pp._run_task)
    assert "_record_skip" in src
    assert "return False  # free providers down -> skip silently" not in src
    rec = inspect.getsource(pp._record_skip)
    assert "prep_last_skip" in rec and "bus.agent" in rec


def test_prep_still_free_only_after_changes():
    """The $0 mandate (DEC-024) must survive every edit."""
    from workers.departments import paused_prep as pp
    src = inspect.getsource(pp)
    assert "free_chat" in src
    for banned in ("council.run", "llm.chat", "anthropic", "_call_paid", "force_paid"):
        assert banned not in src, f"paused prep must stay $0, found {banned!r}"


# ------------------------------------------------- REQ-E2E-1 (end-to-end loop)

class _Tbl:
    def __init__(self, db, name):
        self.db, self.name, self._f = db, name, {}
    def select(self, *a, **k): return self
    def eq(self, k, v): self._f[k] = v; return self
    def in_(self, k, v): self._f[k] = v; return self
    def gte(self, *a, **k): return self
    def lt(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def order(self, *a, **k): return self
    def is_(self, *a, **k): return self
    def insert(self, row):
        self.db.setdefault(self.name, []).append(dict(row)); return self
    def upsert(self, row, **k):
        self.db.setdefault(self.name, []).append(dict(row)); return self
    def update(self, patch):
        for r in self.db.get(self.name, []):
            r.update(patch)
        return self
    def execute(self):
        rows = self.db.get(self.name, [])
        return type("R", (), {"data": rows, "count": len(rows)})()


class _SB:
    def __init__(self): self.db = {}
    def table(self, name): return _Tbl(self.db, name)


def test_e2e_free_exhausted_then_paid_escalation_produces_a_script(monkeypatch):
    """THE test that would have caught the zero-output defect on day one.

    Drive the writer with every free provider failing and assert the item does
    NOT simply get parked for 30 minutes: escalation must fire and a script must
    come back. Before v5.9.6 this test fails — which is exactly the point.
    """
    import workers.departments.creative as cr

    calls = {"free": 0, "paid": 0}

    def fake_write(topic, **kw):
        if kw.get("force_paid"):
            calls["paid"] += 1
            return {"hook": "paid hook", "beats": ["b1", "b2", "b3"]}
        calls["free"] += 1
        raise RuntimeError("council: all free drafts failed -> gemini 429 | groq 403")

    monkeypatch.setattr(cr._brain, "write_script", fake_write)
    monkeypatch.setattr(cr, "ESCALATION_ENABLED", True)
    monkeypatch.setattr(cr, "_sla_state_for", lambda sb, a: "behind")
    monkeypatch.setattr(cr, "kill_switch", lambda: False, raising=False)

    import workers.common as common
    monkeypatch.setattr(common, "kill_switch", lambda: False)
    monkeypatch.setattr(common, "remaining_budget", lambda: 5.0)
    monkeypatch.setattr(common, "remaining_account_budget", lambda sb, a: 20.0)
    monkeypatch.setattr(common, "ceo_decide",
                        lambda *a, **k: {"decision": "allow", "reason": "ok"})
    from agentcore import costmode as cm
    monkeypatch.setattr(cm, "free_only", lambda: False)

    events = []
    class _Bus:
        def agent(self, who, msg, *a, **k): events.append((who, msg))

    class _Job:
        id = "job-e2e"; payload = {}
    sb = _SB()

    script = cr._escalate_to_paid(None, _Job(), None, _Bus(), sb, "Test topic",
                                  "item-1", "acct-1", "proj-1", "free tiers dead")

    assert script is not None, "escalation must produce a script when free capacity is gone"
    assert script["beats"], "escalated script must contain beats"
    assert calls["paid"] == 1, "exactly ONE paid attempt — no spend multiplication"
    assert any("escalat" in m.lower() for _, m in events), "escalation must be announced"


def test_e2e_escalation_refuses_when_guards_say_no(monkeypatch):
    """Same path, but the kill switch is on: no paid call may occur."""
    import workers.departments.creative as cr
    calls = {"paid": 0}

    def fake_write(topic, **kw):
        calls["paid"] += 1
        return {"beats": ["x"]}

    monkeypatch.setattr(cr._brain, "write_script", fake_write)
    import workers.common as common
    monkeypatch.setattr(common, "kill_switch", lambda: True)
    monkeypatch.setattr(common, "remaining_budget", lambda: 5.0)
    monkeypatch.setattr(common, "remaining_account_budget", lambda sb, a: 20.0)

    class _Bus:
        def agent(self, *a, **k): pass
    class _Job:
        id = "j"; payload = {}

    out = cr._escalate_to_paid(None, _Job(), None, _Bus(), _SB(), "t", "i", "a", "p", "err")
    assert out is None
    assert calls["paid"] == 0, "kill switch must prevent any paid model call"


# ------------------------------------------------- REQ-HEALTH-1

def test_heartbeat_pulse_thread_exists_and_is_daemon():
    from workers.departments import ops
    assert callable(ops.start_heartbeat_pulse)
    src = inspect.getsource(ops.start_heartbeat_pulse)
    assert "daemon=True" in src
    assert "except Exception" in src, "telemetry must never crash the worker"


def test_runner_starts_the_pulse():
    import workers.runner as r
    src = inspect.getsource(r.main)
    assert "start_heartbeat_pulse" in src
    assert r.VERSION == "5.9.6"
