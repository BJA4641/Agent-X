"""tests/test_v5_worker.py — smoke tests for the v5 worker engine.

These tests don't require Supabase or API keys. They exercise worker
registration, handler dispatch, job completion, failure paths, and CQO
blocking with a stubbed supabase factory.
"""
from __future__ import annotations
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# In-memory fake Supabase stub for the JobQueue
class _FakeQuery:
    """Chained query builder, returned by table.select/eq/update."""
    def __init__(self, table, is_update=False, patch=None):
        self._t = table
        self._filters = []
        self._limit = 1000
        self._single = False
        self._order = []
        self._is_update = is_update
        self._patch = patch or {}
    def eq(self, k, v): self._filters.append(("eq",k,v)); return self
    def neq(self, k, v): self._filters.append(("neq",k,v)); return self
    def not_(self): return self
    def lte(self, k, v): self._filters.append(("lte",k,v)); return self
    def gte(self, k, v): self._filters.append(("gte",k,v)); return self
    def order(self, *a, **kw): self._order.append(a); return self
    def limit(self, n): self._limit = n; return self
    def in_(self, k, vs): self._filters.append(("in",k,vs)); return self
    def single(self): self._single = True; return self
    def _apply(self, rows):
        out = list(rows)
        for op,k,v in self._filters:
            if op == "eq":   out = [r for r in out if r.get(k) == v]
            elif op == "neq": out = [r for r in out if r.get(k) != v]
            elif op == "lte": out = [r for r in out if float(r.get(k,1e18)) <= v]
            elif op == "gte": out = [r for r in out if float(r.get(k,-1e18)) >= v]
            elif op == "in":  out = [r for r in out if r.get(k) in v]
        return out
    def execute(self):
        if self._is_update:
            matching = self._apply(self._t._rows)
            for r in matching:
                r.update(self._patch)
            data = matching[:]
        else:
            data = self._apply(self._t._rows)
            data.sort(key=lambda r: (-r.get("priority",50), r.get("created_at",0)))
            data = data[:self._limit]
        if self._single:
            class R: pass
            r = R(); r.data = data[0] if data else None; return r
        class R: pass
        r = R(); r.data = data; r.count = len(data); return r


class _FakeTable:
    def __init__(self, name, fake):
        self.name = name
        self.fake = fake
        self._rows = []
    def insert(self, rows):
        if isinstance(rows, dict): rows = [rows]
        for r in rows:
            row = dict(r)
            row.setdefault("created_at", time.time())
            self._rows.append(row)
        # Return a query-like that yields the inserted rows when execute()'d
        q = _FakeQuery(self)
        q._rows_cache = list(self._rows[-len(rows):])
        orig = q.execute
        def exec_insert():
            class R: pass
            r = R(); r.data = list(q._rows_cache); r.count = len(q._rows_cache); return r
        q.execute = exec_insert
        return q
    def upsert(self, rows): return self.insert(rows)
    def update(self, patch):
        return _FakeQuery(self, is_update=True, patch=patch)
    def select(self, *a, **kw):
        return _FakeQuery(self)


class _FakeStorage:
    def from_(self, b): return self
    def upload(self, *a, **kw): pass
    def get_public_url(self, n): return f"https://fake.storage/{n}"


class _FakeSB:
    def __init__(self):
        self.tables = {}
    def table(self, name):
        return self.tables.setdefault(name, _FakeTable(name, self))
    def rpc(self, name, params):
        class R:
            def execute(self): return self
        return R()
    def storage(self):
        return _FakeStorage()


@pytest.fixture
def fake_sb_factory():
    fake = _FakeSB()
    return lambda: fake


def test_worker_registers_and_runs_handler(fake_sb_factory, monkeypatch):
    """End-to-end: enqueue a job, worker claims it, handler fires, job completes."""
    from agentcore import JobQueue, Worker, Job, JobStatus, Priority, get_bus
    from agentcore.runtime import reset_runtime_for_tests
    reset_runtime_for_tests()
    bus = get_bus()
    # Silence bus persister during unit test
    bus.set_persister(lambda e: None)

    q = JobQueue(supabase_factory=fake_sb_factory)
    w = Worker(q, name="test-worker", poll_interval=0.01)
    w.set_deps(supabase=fake_sb_factory, bus=bus)

    seen = []
    def handler(worker, job, ctx):
        seen.append(job.id)
        worker.queue.complete(job, {"ok": True, "saw": True})
    w.register("test.ping", handler)

    j = Job(job_type="test.ping", payload={"hi": True}, priority=Priority.HIGH)
    q.enqueue(j)

    # Drive the worker manually (one claim)
    jobs = q.claim("test-worker", job_types=["test.ping"], limit=1)
    assert len(jobs) == 1
    w._execute(jobs[0])
    assert seen == [j.id]
    assert jobs[0].status == JobStatus.DONE


def test_cfo_blocks_when_killswitch_on(monkeypatch):
    from workers.departments import finance
    from agentcore import JobQueue, Worker, Job, JobStatus
    from agentcore.runtime import reset_runtime_for_tests
    reset_runtime_for_tests()

    sb = _FakeSB()
    q = JobQueue(supabase_factory=lambda: sb)
    w = Worker(q, name="cfo-test", poll_interval=0.01)
    w.set_deps(supabase=lambda: sb, bus=_silent_bus())
    finance.register(w)

    # Kill switch is checked via workers.common.kill_switch AND finance.kill_switch
    import workers.common as _c
    monkeypatch.setattr(_c, "kill_switch", lambda: True)
    monkeypatch.setattr("workers.departments.finance.kill_switch", lambda: True)
    j = Job(job_type="cfo.preflight", payload={})
    q.enqueue(j)
    claimed = q.claim("cfo-test", job_types=["cfo.preflight"])[0]
    w._execute(claimed)
    assert claimed.status == JobStatus.FAILED  # fatal block
    assert "KILL SWITCH" in (claimed.error or "").upper() or "CFO BLOCK" in (claimed.error or "").upper()


def test_cqo_rejects_after_max_rewrites(monkeypatch):
    """CQO must cap rewrites at MAX_REWRITES and final-reject — no infinite loop."""
    from workers.departments import cqo
    from agentcore import JobQueue, Worker, Job, JobStatus
    from agentcore.runtime import reset_runtime_for_tests
    reset_runtime_for_tests()

    sb = _FakeSB()
    q = JobQueue(supabase_factory=lambda: sb)
    w = Worker(q, name="cqo-test", poll_interval=0.01)
    w.set_deps(supabase=lambda: sb, bus=_silent_bus())

    # Stub grader to always return failing grade
    def fake_grade(*a, **kw):
        return {"overall": 4.0, "passed": False,
                "scores": {"hook":4,"visuals":4,"pacing":4,"audio":4,"caption":4,"cta":4},
                "notes": "boring", "fix": "make it better", "fix_instruction": "make it better"}
    import agent.grader as _real_grader
    import workers.departments.cqo as _cqo_mod
    monkeypatch.setattr(_real_grader, "grade_post", fake_grade)
    # Also mute memory.add
    import agentcore.memory as _m
    monkeypatch.setattr(_m, "add", lambda **kw: {})
    # Patch board_patch to be a no-op (FakeSB board_items table doesn't pre-exist)
    import workers.common as _cm
    monkeypatch.setattr(_cm, "board_patch", lambda *a, **kw: None)

    cqo.register(w)
    j = Job(job_type="cqo.grade_script", payload={
        "script": {"title": "x", "hook": "hi", "beats": [
            {"voiceover":"a","visual_prompt":"vp","duration_ms":3000}]*5, "cta":"follow"},
        "rewrite_attempt": 2,  # already at cap
    })
    q.enqueue(j)
    claimed = q.claim("cqo-test", job_types=["cqo.grade_script"])[0]
    w._execute(claimed)
    assert claimed.status == JobStatus.DONE
    assert claimed.result.get("rejected") is True


def test_department_registers_all_handlers():
    """register_all() should register >=10 job types without import errors."""
    from workers.departments import register_all
    from agentcore import JobQueue, Worker
    from agentcore.runtime import reset_runtime_for_tests
    reset_runtime_for_tests()
    q = JobQueue(supabase_factory=lambda: _FakeSB())
    w = Worker(q, name="reg-test", poll_interval=0.01)
    w.set_deps(supabase=lambda: _FakeSB(), bus=_silent_bus())
    register_all(w)
    assert len(w.handlers) >= 12  # one per registered job


def _silent_bus():
    from agentcore import Bus
    b = Bus(); b.set_persister(lambda e: None); return b
