"""agentcore — production-grade agent primitives for Agent-X.

A typed, observable, budget-guarded kernel on which every agent in the
company runs. Used by workers/* to implement the v2 blueprint.
"""
from .config import get, supabase, has_supabase, TENANT_ID, DAILY_BUDGET_USD, kill_switch_on, soft_pause_on
from .runtime import Runtime, get_runtime, reset_runtime_for_tests
from .models import (
    AgentContext, Job, JobStatus, Event, EventType, AgentResult,
    QualityGate, CostQuote, HumanEscalation, RetryableError, FatalError,
    Priority,
)
from .bus import Bus, get_bus
from .jobs import JobQueue
from .llm import ModelRouter, llm_call, llm_json, get_router, estimate_cost, TIERS
from .guards import cost_guard, circuit_breaker, handle_circuit_open, get_cost_guard
from .observability import Span, get_tracer, Tracer, recent_traces
from .agent import BaseAgent
from .worker import Worker
from .validators import (
    Beat, Script, SEOPack, GradeResult, PlatformCaptions,
    BrandBible, validate_dangerous_content, DimensionScore,
)

__all__ = [
    # config
    "get", "supabase", "has_supabase", "TENANT_ID", "DAILY_BUDGET_USD", "kill_switch_on", "soft_pause_on",
    # runtime
    "Runtime", "get_runtime", "reset_runtime_for_tests",
    # models
    "AgentContext", "Job", "JobStatus", "Event", "EventType", "AgentResult",
    "QualityGate", "CostQuote", "HumanEscalation", "RetryableError", "FatalError",
    "Priority",
    # plumbing
    "Bus", "get_bus", "JobQueue",
    "ModelRouter", "llm_call", "llm_json", "get_router", "estimate_cost", "TIERS",
    "cost_guard", "circuit_breaker", "handle_circuit_open", "get_cost_guard",
    "Span", "get_tracer", "Tracer", "recent_traces",
    "BaseAgent", "Worker",
    # validators / schemas
    "Beat", "Script", "SEOPack", "GradeResult", "PlatformCaptions",
    "BrandBible", "validate_dangerous_content", "DimensionScore",
]
