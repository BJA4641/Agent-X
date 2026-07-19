"""departments/__init__.py — Phase 3: register all departments."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agentcore import Worker

from . import finance, portfolio, research, editorial, creative, postprod
from . import distribution, analytics, cqo, risk, knowledge
from . import ops, human_desk, experiments, brand_studio, monetization


def register_all(worker: "Worker"):
    # Core governance (register first so preflight is ready)
    finance.register(worker)
    cqo.register(worker)
    risk.register(worker)
    # Brand (must run before editorial so bible is ready)
    brand_studio.register(worker)
    # Production pipeline
    portfolio.register(worker)
    research.register(worker)
    editorial.register(worker)
    creative.register(worker)
    postprod.register(worker)
    monetization.register(worker)
    distribution.register(worker)
    analytics.register(worker)
    knowledge.register(worker)
    # Phase 3 additions
    ops.register(worker)
    human_desk.register(worker)
    experiments.register(worker)
