"""test_v6_contracts.py — contract tests that call REAL functions with the
REAL arguments production passes. These are the tests that would have caught
the v5.5.1 outage (7,220 identical TypeErrors) before deploy.

Rule these tests enforce: a caller and a callee must be tested TOGETHER.
No source-grepping, no theater — actual invocation.
"""
import inspect
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------- brain contract

def test_write_script_accepts_grade_feedback_kwarg():
    """The exact kwarg creative.py passes must exist in brain.write_script.
    v5.5.1 shipped without this and failed 7,220 times in production."""
    from agent import brain
    sig = inspect.signature(brain.write_script)
    assert "grade_feedback" in sig.parameters, (
        "brain.write_script must accept grade_feedback= — "
        "creative.write_script passes it on every rewrite")


def test_write_script_real_invocation_with_grade_feedback(monkeypatch):
    """Actually CALL brain.write_script the way creative.py calls it.
    LLM/grader/memory/config are stubbed so no network or DB is touched,
    but the call path (signature, feedback merge, normalize, grade) is real."""
    from agent import brain

    monkeypatch.setattr(brain.llm, "ready", lambda: False)          # demo-script path
    monkeypatch.setattr(brain.ledger, "record", lambda *a, **k: None)
    monkeypatch.setattr(brain.ledger, "budget_ok", lambda *a, **k: False)
    monkeypatch.setattr(brain.memory, "load_grade_feedback", lambda *a, **k: "mem-note")
    monkeypatch.setattr(brain.memory, "context_block", lambda *a, **k: "")
    monkeypatch.setattr(brain.config, "load_prompt", lambda name: ("{topic}", "test-v"))
    monkeypatch.setattr(brain, "_load_brand_context", lambda *a, **k: {})
    monkeypatch.setattr(brain, "_niche_for_account", lambda *a, **k: "ai")
    monkeypatch.setattr(
        brain.grader_mod, "grade_post",
        lambda script, **k: {"passed": True, "overall": 9.0, "fix": "",
                             "scores": {}, "notes": ""})

    script = brain.write_script(
        "test topic", item_id=None, account_id=None, project_id=None,
        grade_feedback="fix the hook",   # <- the production kwarg
    )
    assert isinstance(script, dict)
    assert script.get("beats"), "write_script must return a script with beats"


def test_creative_call_kwargs_match_brain_signature():
    """Every kwarg creative.write_script passes to brain.write_script must be
    accepted by brain.write_script's signature. Catches the next drift."""
    from agent import brain
    sig = inspect.signature(brain.write_script)
    for kw in ("item_id", "account_id", "project_id", "grade_feedback"):
        assert kw in sig.parameters, f"brain.write_script missing kwarg: {kw}"


# ---------------------------------------------------------------- inflight contract

class _FakeQuery:
    def __init__(self, log):
        self.log = log
        self.count = 7

    def select(self, *a, **k):
        self.log.append(("select", a, k)); return self

    def in_(self, col, vals):
        self.log.append(("in_", col, tuple(vals))); return self

    def eq(self, *a):
        self.log.append(("eq", a)); return self

    def or_(self, *a):
        self.log.append(("or_", a)); return self

    def execute(self):
        return self


class _FakeSB:
    def __init__(self):
        self.log = []

    def table(self, name):
        self.log.append(("table", name)); return _FakeQuery(self.log)


def test_count_inflight_uses_in_filter():
    """v5.5.1 chained .eq('status','idea').or_(...) which ANDs in supabase-py,
    matched zero rows, and let ideation flood 7,307 items. The fix must use
    .in_() across all four in-flight statuses — and actually return the count."""
    from workers.departments import portfolio
    sb = _FakeSB()
    n = portfolio._count_inflight(sb, "acct-1")
    assert n == 7, "inflight count must come from the query, not swallow to 0"
    in_calls = [c for c in sb.log if c[0] == "in_"]
    assert in_calls, "_count_inflight must filter with .in_(...)"
    assert set(in_calls[0][2]) == {"idea", "drafted", "approved", "scheduled"}
    assert not [c for c in sb.log if c[0] == "or_"], "or_ after eq is the flood bug"


# ---------------------------------------------------------------- breaker contract

class _FakeJob:
    def __init__(self, job_type):
        self.id = "j-" + job_type
        self.job_type = job_type
        self.payload = {}
        self.brand_id = None
        self.account_id = None
        self.project_id = None
        self.priority = 50
        self.cost_cents = 0
        self.status = None
        self.result = None


class _FakeQueue:
    def __init__(self):
        self.updates = []

    def fail(self, job, reason, fatal=False):
        self.updates.append(("fail", job.job_type, reason))

    def _update_row(self, job, patch):
        self.updates.append(("update", job.job_type, patch))


def test_circuit_breaker_trips_after_identical_failures():
    """5 identical consecutive failures on one job_type must open the breaker;
    the next job of that type must be parked, not executed."""
    from agentcore.worker import Worker
    w = Worker.__new__(Worker)          # no queue thread, just the fields we need
    w.queue = _FakeQueue()
    w.bus = types.SimpleNamespace(agent=lambda *a, **k: None)
    w._ctx = types.SimpleNamespace(deps={})
    w._fail_streaks = {}
    w._breaker_until = {}
    w.BREAKER_THRESHOLD = 5
    w.BREAKER_HOLD_S = 1800

    for _ in range(5):
        w._record_failure(_FakeJob("creative.write_script"),
                          "TypeError: unexpected keyword argument 'grade_feedback'")

    until = w._breaker_until.get("creative.write_script", 0)
    assert until > time.time(), "breaker must be open after 5 identical failures"

    # A different error signature resets the streak instead of stacking
    w._record_failure(_FakeJob("publisher.post"), "err A")
    w._record_failure(_FakeJob("publisher.post"), "err B")
    assert w._fail_streaks["publisher.post"]["n"] == 1


# ---------------------------------------------------------------- idempotency contract

class _IdemTable:
    """Fake jobs table: one stored row with a DONE status + given key."""
    def __init__(self, key, status):
        self.row = {"id": "old", "job_type": "ops.heartbeat", "status": status,
                    "idempotency_key": key, "payload": {}, "priority": 50,
                    "attempts": 0, "max_attempts": 2}
        self.inserted = []
        self._match = None

    # query chain
    def select(self, *a, **k): return self
    def eq(self, col, val):
        self._match = (self.row if col == "idempotency_key"
                       and val == self.row["idempotency_key"] else None)
        return self
    def in_(self, col, vals):
        if self._match and self._match.get(col) not in vals:
            self._match = None
        return self
    def not_(self): return self
    def limit(self, n): return self
    def execute(self):
        return types.SimpleNamespace(data=[self._match] if self._match else [])
    def insert(self, row):
        self.inserted.append(row); return self


def _mk_queue(table):
    from agentcore.jobs import JobQueue
    q = JobQueue.__new__(JobQueue)
    q._sb = lambda: types.SimpleNamespace(table=lambda name: table)
    q._bus = types.SimpleNamespace(emit=lambda *a, **k: None,
                                    agent=lambda *a, **k: None)
    return q


def test_done_job_does_not_block_reenqueue():
    """v5.6.1: the heartbeat-killer. A DONE job sharing the idempotency key
    must NOT block enqueueing the successor (this froze worker_health forever)."""
    from agentcore.models import Job
    table = _IdemTable("hb:agentx-v5:12345", "done")
    q = _mk_queue(table)
    q.enqueue(Job(job_type="ops.heartbeat", payload={},
                  idempotency_key="hb:agentx-v5:12345"))
    assert table.inserted, "successor must be inserted when prior job is done"


def test_queued_job_still_blocks_duplicate():
    """Idempotency must still dedupe genuinely pending work."""
    from agentcore.models import Job
    table = _IdemTable("tick:999", "queued")
    q = _mk_queue(table)
    q.enqueue(Job(job_type="portfolio.tick", payload={},
                  idempotency_key="tick:999"))
    assert not table.inserted, "queued duplicate must NOT be re-inserted"


# ---------------------------------------------------------------- eleven env contract

def test_eleven_key_accepts_both_env_names(monkeypatch):
    """Docs said ELEVEN_API_KEY; code read ELEVENLABS_API_KEY. Both must work."""
    from agent import voice
    monkeypatch.setattr(voice.config, "get",
                        lambda k, d=None: "k1" if k == "ELEVENLABS_API_KEY" else None)
    assert voice.eleven_key() == "k1"
    monkeypatch.setattr(voice.config, "get",
                        lambda k, d=None: "k2" if k == "ELEVEN_API_KEY" else None)
    assert voice.eleven_key() == "k2"


def test_eleven_daily_char_cap(monkeypatch):
    from agent import voice
    monkeypatch.setattr(voice.config, "get",
                        lambda k, d=None: "100" if k == "ELEVEN_DAILY_CHAR_CAP" else d)
    voice._ELEVEN_DAY["day"] = None; voice._ELEVEN_DAY["used"] = 0
    assert voice.eleven_chars_ok(80)
    voice.eleven_chars_add(80)
    assert not voice.eleven_chars_ok(30), "cap must block once exceeded"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


# ---------------------------------------------------------------- soft pause contract

def test_soft_pause_reads_settings(monkeypatch):
    """v5.7: soft_pause_on() must reflect the settings row the web UI writes."""
    from agentcore import config as cfg

    class _T:
        def __init__(self, on): self.on = on
        def select(self, *a): return self
        def eq(self, *a): return self
        def execute(self):
            return types.SimpleNamespace(data=[{"value": {"on": self.on}}])

    for flag in (True, False):
        monkeypatch.setattr(cfg, "supabase",
                            lambda f=flag: types.SimpleNamespace(table=lambda n: _T(f)))
        assert cfg.soft_pause_on() is flag


# ---------------------------------------------------------------- v5.7.1 quality contracts

def test_generic_ai_filter_blocks_offniche_topics():
    """v5.7.1: skincare/pet accounts must never receive generic-AI topics."""
    from workers.departments.editorial import _is_generic_ai
    assert _is_generic_ai(" 3 free ai tools that replace paid apps ")
    assert _is_generic_ai(" the ai setting everyone should turn off ")
    assert _is_generic_ai(" i asked chatgpt to plan my week ")
    assert not _is_generic_ai(" 3 skincare mistakes that age you faster ")
    assert not _is_generic_ai(" the toy cats go crazy for that costs $0 ")


def test_grader_skip_never_fakes_scores(monkeypatch):
    """v5.7.1: when LLM/budget gate is closed, grader must mark skipped=True."""
    from agent import grader as g
    monkeypatch.setattr(g.llm, "ready", lambda: False)
    monkeypatch.setattr(g, "_save_grade", lambda *a, **k: None)
    monkeypatch.setattr(g.events, "emit", lambda *a, **k: None)
    monkeypatch.setattr(g.memory, "context_block", lambda *a, **k: "")
    monkeypatch.setattr(g.memory, "load_grade_feedback", lambda *a, **k: "")
    monkeypatch.setattr(g.memory, "remember", lambda *a, **k: None, raising=False)
    v = g.grade_post({"hook": "x", "beats": [{"vo": "y"}]})
    assert v.get("skipped") is True
    assert v.get("passed") is False
