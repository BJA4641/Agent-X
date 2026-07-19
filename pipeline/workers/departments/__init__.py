"""departments/ — per-blueprint department agents.

Each module exposes a register(worker) function that attaches its handlers
to a Worker. register_all() wires them all. Handlers are thin adapters over
the production-tested functions in `agent/`.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agentcore import Worker

from . import finance, portfolio, research, editorial, creative, postprod
from . import distribution, analytics, cqo, risk, knowledge


def register_all(worker: "Worker"):
    """Import order only affects log readability; the bus decouples deps."""
    finance.register(worker)
    cqo.register(worker)
    risk.register(worker)
    portfolio.register(worker)
    research.register(worker)
    editorial.register(worker)
    creative.register(worker)
    postprod.register(worker)
    distribution.register(worker)
    analytics.register(worker)
    knowledge.register(worker)
