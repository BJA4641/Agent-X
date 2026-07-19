"""bus.py — Event bus.

Agents emit events; other agents subscribe. This decouples departments.
Also persists to Supabase agent_events (for the dashboard feed).
"""
from __future__ import annotations
import time, threading, traceback
from typing import Callable, Dict, List
from collections import defaultdict
from .models import Event, EventType


class Bus:
    def __init__(self):
        self._subs: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._persist: Callable[[Event], None] | None = None

    def set_persister(self, fn: Callable[[Event], None]):
        self._persist = fn

    def on(self, event_type: str | EventType, handler: Callable[[Event], None]):
        key = event_type.value if isinstance(event_type, EventType) else event_type
        with self._lock:
            self._subs[key].append(handler)

    def emit(self, event: Event):
        key = event.type.value if isinstance(event.type, EventType) else event.type
        # Persist first (so the dashboard feed is always updated even if a handler throws)
        if self._persist:
            try:
                self._persist(event)
            except Exception:
                traceback.print_exc()
        handlers = []
        with self._lock:
            handlers = list(self._subs.get(key, [])) + list(self._subs.get("*", []))
        for h in handlers:
            try:
                h(event)
            except Exception:
                traceback.print_exc()

    # Convenience emitters
    def agent(self, emitter: str, message: str, status: str = "info",
              action: str = "", job_id: str = None, **extra) -> Event:
        e = Event(
            emitter=emitter, type=EventType.AGENT_INFO,
            status=status, action=action, message=message,
            job_id=job_id, data=extra, ts=time.time(),
        )
        self.emit(e)
        return e

    def cost(self, emitter: str, amount_cents: int, detail: str = "", job_id: str = None):
        self.emit(Event(
            emitter=emitter, type=EventType.COST_INCURRED,
            status="info", action="cost", message=f"spent ${amount_cents/100:.4f} {detail}",
            cost_cents=amount_cents, job_id=job_id,
        ))

    def job(self, job, type_: EventType, message: str = "", emitter: str = "system"):
        self.emit(Event(
            emitter=emitter, type=type_, message=message or f"job {type_.value}",
            job_id=job.id if hasattr(job, "id") else job.get("id"),
            brand_id=getattr(job, "brand_id", None), account_id=getattr(job, "account_id", None),
        ))


# Singleton
_bus = Bus()


def get_bus() -> Bus:
    return _bus
