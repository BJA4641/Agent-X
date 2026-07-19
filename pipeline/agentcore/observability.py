"""observability.py — tracing/spans for agent calls.

Like LangSmith / Pydantic Logfire but tiny and local. Every agent call gets a
span with timing, inputs/outputs truncated, cost, tokens, success/failure.
Spans nest via context vars for a call tree.
"""
from __future__ import annotations
import time, contextvars, contextlib, uuid, json
from typing import Any, Dict, List, Optional

_current_span: contextvars.ContextVar = contextvars.ContextVar("current_span", default=None)


class Span:
    def __init__(self, name: str, agent: str = "", parent: Optional["Span"] = None,
                 extra: Dict[str, Any] = None):
        self.id = uuid.uuid4().hex[:10]
        self.name = name
        self.agent = agent
        self.parent = parent
        self.started = time.time()
        self.finished: Optional[float] = None
        self.annotations: Dict[str, Any] = extra or {}
        self.children: List[Span] = []
        self.error: Optional[str] = None
        self.status: str = "ok"

    def annotate(self, key: str, val: Any):
        self.annotations[key] = _jsonable(val)

    def fail(self, err: str):
        self.error = err
        self.status = "error"

    def end(self):
        self.finished = time.time()

    @property
    def duration_ms(self) -> float:
        end = self.finished or time.time()
        return (end - self.started) * 1000

    def to_dict(self, max_depth=4):
        d = {
            "id": self.id, "name": self.name, "agent": self.agent,
            "status": self.status, "duration_ms": round(self.duration_ms,1),
            "annotations": self.annotations,
        }
        if self.error:
            d["error"] = self.error
        if self.children and max_depth > 0:
            d["children"] = [c.to_dict(max_depth-1) for c in self.children]
        return d


_tracer_root: List[Span] = []   # in-memory (last N runs); also persisted via bus


def get_tracer():
    return Tracer()


class Tracer:
    @contextlib.contextmanager
    def span(self, name: str, agent: str = "", **extra):
        parent = _current_span.get()
        s = Span(name=name, agent=agent, parent=parent, extra=extra)
        tok = _current_span.set(s)
        if parent:
            parent.children.append(s)
        else:
            _tracer_root.append(s)
            if len(_tracer_root) > 200:
                _tracer_root.pop(0)
        try:
            yield s
        except Exception as e:
            s.fail(str(e)[:400])
            raise
        finally:
            s.end()
            _current_span.reset(tok)


def current_span() -> Optional[Span]:
    return _current_span.get()


def recent_traces(n: int = 20) -> List[dict]:
    return [s.to_dict() for s in _tracer_root[-n:]]


def _jsonable(v: Any) -> Any:
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)[:500]
