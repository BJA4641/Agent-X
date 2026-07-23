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
