"""departments/__init__.py — Phase 3: register all departments."""
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from agentcore import Worker

from . import finance, portfolio, research, editorial, creative, postprod
from . import distribution, analytics, cqo, risk, knowledge
from . import ops, human_desk, experiments, brand_studio, monetization, ceo
from . import providers  # v5.8.7 provider probe (keys, liveness, balances)
from . import strategy   # v5.8.8 10-day paid audit + arena leaderboard scout
from . import sla         # v5.9.5 publishing SLA plan/monitor/self-heal
from . import paused_prep # v5.9.5 $0 free-only prep for paused accounts
from . import art_director  # v5.10.0 shot-level prompt packs
from . import scorecard     # v5.11.13 measurable improvement


def register_all(worker: "Worker"):
    # Core governance (register first so preflight is ready)
    finance.register(worker)
    cqo.register(worker)
    risk.register(worker)
    ceo.register(worker)   # v5.5: CEO gates every spend decision
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
    # Phase 3+ additions
    ops.register(worker)
    human_desk.register(worker)
    experiments.register(worker)
    providers.register(worker)  # v5.8.7
    strategy.register(worker)   # v5.8.8
    sla.register(worker)        # v5.9.5
    paused_prep.register(worker)  # v5.9.5
    art_director.register(worker)  # v5.10.0
    scorecard.register(worker)     # v5.11.13
