"""agentcore/runtime.py — bootstraps the runtime (bus, queue, router, deps).

Wires everything together once at worker start so handlers and the CLI can
share the same objects.
"""
from __future__ import annotations
import os, traceback, time
from typing import Dict, Any

from .bus import get_bus
from .jobs import JobQueue
from .llm import get_router
from .guards import get_cost_guard
from .observability import Tracer
from .events import wire_bus_to_persistence, seed_feed_if_empty
from . import config as _cfg


class Runtime:
    def __init__(self):
        self.bus = get_bus()
        self.sb_factory = _cfg.supabase  # lazy per-call factory
        self.queue = JobQueue(supabase_factory=self.sb_factory)
        self.router = get_router()
        self.cost_guard = get_cost_guard()
        self.tracer = Tracer()
        self.deps: Dict[str, Any] = {
            "bus": self.bus,
            "queue": self.queue,
            "router": self.router,
            "tracer": self.tracer,
            "cost_guard": self.cost_guard,
            "supabase": self.sb_factory,
        }

    def boot(self):
        """Wire persistence, ensure tables, seed UI feed."""
        wire_bus_to_persistence(self.bus)
        # Best-effort schema bootstrap (tables that didn't exist in v4.3)
        try:
            self.queue.ensure_tables()
        except Exception as e:
            print(f"[runtime] table bootstrap non-fatal: {e}")
        seed_feed_if_empty(self.bus)
        self.bus.agent("system",
                       f"Runtime online. tenant={_cfg.TENANT_ID} "
                       f"budget=${_cfg.DAILY_BUDGET_USD:.2f} "
                       f"kill_switch={'ON' if _cfg.kill_switch_on() else 'off'}",
                       "success", "boot")
        return self


_singleton: Runtime | None = None


def get_runtime() -> Runtime:
    global _singleton
    if _singleton is None:
        _singleton = Runtime().boot()
    return _singleton


def reset_runtime_for_tests():
    global _singleton
    _singleton = None
