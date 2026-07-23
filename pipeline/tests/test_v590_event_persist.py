"""v5.9.0 — guard the agent_events persister contract.

Production bug this locks down: agent_events.id is GENERATED ALWAYS AS IDENTITY,
so Postgres rejects any explicit id (SQLSTATE 428C9). The persister sent one on
every event, so 100% of department events were dropped and the workspace feed
looked dead for weeks.
"""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentcore import events as ev
from agentcore.models import Event, EventType


class _FakeTable:
    def __init__(self, sink): self.sink = sink
    def insert(self, row): self.sink.append(row); return self
    def upsert(self, row, **kw): return self
    def execute(self): return type("R", (), {"data": []})()


class _FakeSB:
    def __init__(self): self.rows = []
    def table(self, name): return _FakeTable(self.rows)


def _persist(monkeypatch):
    sb = _FakeSB()
    monkeypatch.setattr(ev, "_sb", lambda: sb)
    e = Event(emitter="ceo", type=EventType.AGENT_INFO, status="warn",
              action="tick_budget", message="daily budget exhausted",
              ts=time.time(), cost_cents=25)
    ev.persist_to_agent_events(e)
    assert sb.rows, "nothing was persisted"
    return sb.rows[0]


def test_never_sends_identity_id(monkeypatch):
    row = _persist(monkeypatch)
    assert "id" not in row, "id is GENERATED ALWAYS AS IDENTITY — sending it fails every insert"


def test_writes_agent_column(monkeypatch):
    row = _persist(monkeypatch)
    assert row["agent"] == "ceo", "the dashboard groups by `agent`, not `emitter`"
    assert row["emitter"] == "ceo"


def test_writes_cost_usd(monkeypatch):
    row = _persist(monkeypatch)
    assert row["cost_usd"] == 0.25, "the feed sums cost_usd"
    assert row["cost_cents"] == 25


def test_status_is_constraint_safe(monkeypatch):
    sb = _FakeSB()
    monkeypatch.setattr(ev, "_sb", lambda: sb)
    e = Event(emitter="cqo", type=EventType.AGENT_INFO, status="critical",
              action="x", message="m", ts=time.time())
    ev.persist_to_agent_events(e)
    # ae_status_check allows only info/success/warn/error/debate
    assert sb.rows[0]["status"] in ("info", "success", "warn", "error", "debate")


def test_action_never_null(monkeypatch):
    sb = _FakeSB()
    monkeypatch.setattr(ev, "_sb", lambda: sb)
    e = Event(emitter="coo", type=EventType.AGENT_INFO, status="info",
              action="", message="m", ts=time.time())
    ev.persist_to_agent_events(e)
    assert sb.rows[0]["action"], "action is NOT NULL in the table"


# ---- v5.9.3: guard against calling APIs that do not exist ----
def test_runtime_has_no_supabase_or_bus_helpers():
    """council/costmode must not call runtime.supabase() or runtime.bus().
    Both were invented, both raised AttributeError, and both were swallowed —
    silently disabling model discovery AND failure reporting for two releases."""
    from agentcore import runtime
    assert not hasattr(runtime, "supabase"), "runtime.supabase() exists now — update callers"
    assert not hasattr(runtime, "bus"), "runtime.bus() exists now — update callers"

def _code_only(mod):
    """Source with comments stripped — we assert on real calls, not prose."""
    import inspect
    return "\n".join(l.split("#")[0] for l in inspect.getsource(mod).splitlines())

def test_council_uses_working_supabase_accessor():
    from agentcore import council
    src = _code_only(council)
    assert "runtime.supabase()" not in src, "council still calls a non-existent API"
    assert "runtime.bus()" not in src, "council still calls a non-existent API"

def test_brain_reports_the_real_write_error():
    from agent import brain
    src = _code_only(brain)
    assert "council+fallback failed" not in src, "generic error message is back"
    assert "_write_err" in src, "brain must carry the underlying provider error"
