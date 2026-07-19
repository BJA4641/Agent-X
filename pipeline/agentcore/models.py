"""models.py — typed core models (Pydantic) for agentcore.

Inspired by PydanticAI typed results + LangGraph state + CrewAI task model.
Every input/output/state in the system is one of these types. This single
file is the schema of the company.
"""
from __future__ import annotations
import time, uuid, json
from enum import Enum
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


# ---------- Enums ----------

class JobStatus(str, Enum):
    QUEUED       = "queued"
    CLAIMED      = "claimed"
    IN_PROGRESS  = "in_progress"
    WAIT_HUMAN   = "wait_human"   # paused on HumanEscalation
    DONE         = "done"
    FAILED       = "failed"      # exhausted retries → dead-letter
    BLOCKED      = "blocked"     # blocked by CQO / missing dependency


class EventType(str, Enum):
    # Lifecycle
    JOB_CREATED   = "job.created"
    JOB_STARTED   = "job.started"
    JOB_DONE      = "job.done"
    JOB_FAILED    = "job.failed"
    JOB_BLOCKED   = "job.blocked"
    # Agent chatter
    AGENT_START   = "agent.start"
    AGENT_INFO    = "agent.info"
    AGENT_WARN    = "agent.warn"
    AGENT_OK      = "agent.ok"
    AGENT_ERR     = "agent.error"
    # Content lifecycle
    BRIEF_READY    = "brief.ready"
    SCRIPT_READY   = "script.ready"
    VIDEO_READY    = "video.ready"
    QUALITY_PASS   = "quality.pass"
    QUALITY_FAIL   = "quality.fail"
    PUBLISHED      = "content.published"
    METRICS_24H    = "metrics.24h"
    # System
    COST_INCURRED  = "cost.incurred"
    BUDGET_HIT     = "budget.hit"
    HUMAN_NEEDED   = "human.needed"
    HUMAN_RESOLVED = "human.resolved"
    RISK_FLAG      = "risk.flag"
    MEMORY_STORED  = "memory.stored"


class Priority(int):
    LOW = 10
    NORMAL = 50
    HIGH = 80
    TREND_JACK = 95
    EMERGENCY = 100


# ---------- Structured results ----------

class CostQuote(BaseModel):
    est_cost_usd: float = Field(..., ge=0, description="Estimated USD cost of this job")
    model_tier: str = Field("standard", description="cheap | standard | premium")
    token_estimate: int = 0


class QualityGate(BaseModel):
    """CQO-style check result."""
    passed: bool
    score: float = Field(..., ge=0, le=10)
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    fix_instruction: Optional[str] = None
    blocker: bool = Field(False, description="If true, cannot proceed without fix")


class HumanEscalation(Exception):
    """Raise from an agent to pause the job and wait for a human."""
    def __init__(self, *, severity: str = "ask", summary: str,
                 options: Optional[List[Dict[str,str]]] = None,
                 context: Optional[Dict[str,Any]] = None,
                 deadline_hours: float = 24.0):
        self.severity = severity
        self.summary = summary
        self.options = options or [{"label":"Approve","effect":"approve"},{"label":"Reject","effect":"reject"}]
        self.context = context or {}
        self.deadline_hours = deadline_hours
        super().__init__(summary)


class RetryableError(Exception):
    """Raise when the operation might succeed on retry (503, timeout, rate-limit)."""
    def __init__(self, msg: str, delay_s: float = 5.0):
        self.delay_s = delay_s
        super().__init__(msg)


class FatalError(Exception):
    """Raise when retrying won't help (schema bug, bad input, hard failure)."""
    pass


# ---------- Core state objects ----------

class AgentContext(BaseModel):
    """Dependency-injection container passed to every agent."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    job_id: Optional[str] = None
    brand_id: Optional[str] = None
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    priority: int = Priority.NORMAL
    # deps (filled at runtime; set arbitrary_types_allowed so we can pass supabase/logger)
    deps: Dict[str, Any] = Field(default_factory=dict)

    def dep(self, key: str, default: Any = None) -> Any:
        return self.deps.get(key, default)

    def child(self, **overrides) -> "AgentContext":
        d = self.model_dump()
        d["deps"] = dict(self.deps)
        d.update(overrides)
        return AgentContext(**d)


class Job(BaseModel):
    """A durable unit of work. Persisted in Postgres. Replaces ad-hoc board_items."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    job_type: str
    brand_id: Optional[str] = None
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    priority: int = Priority.NORMAL
    status: JobStatus = JobStatus.QUEUED
    payload: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    attempts: int = 0
    max_attempts: int = 2
    parent_job_id: Optional[str] = None
    requested_by: str = "system"
    scheduled_for: float = Field(default_factory=time.time)
    deadline: Optional[float] = None
    error: Optional[str] = None
    cost_cents: int = 0
    created_at: float = Field(default_factory=time.time)
    claimed_at: Optional[float] = None
    finished_at: Optional[float] = None
    idempotency_key: Optional[str] = None   # same key → existing job returned, not duplicated


class Event(BaseModel):
    """One line in the agent event stream (agent_events table)."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = Field(default_factory=time.time)
    emitter: str
    type: EventType
    status: str = "info"   # info | success | warn | error
    action: str = ""       # short machine-readable code ("script_start")
    message: str
    subject: Dict[str, Any] = Field(default_factory=dict)
    job_id: Optional[str] = None
    brand_id: Optional[str] = None
    account_id: Optional[str] = None
    cost_cents: int = 0
    data: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Every agent returns this."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    ok: bool
    output: Dict[str, Any] = Field(default_factory=dict)
    events: List[Any] = Field(default_factory=list)
    cost_cents: int = 0
    quality: Optional[QualityGate] = None
    escalate: Optional[Any] = None
    next_jobs: List[Any] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
