"""agent.py — BaseAgent class that every agent inherits from.

Inspired by CrewAI's Agent class + PydanticAI's Agent (dependency injection +
result validators) + LangGraph's state nodes.

Subclasses implement run(ctx, job) and can call:
  * self.llm(prompt, tier=..., system=...)              -> raw text
  * self.llm_structured(prompt, result_type=..., ...)  -> Pydantic-validated object
  * self.emit_info/warn/ok/err(...)                    -> events onto bus
  * self.spawn(job_type, payload, ...)                 -> follow-up jobs
  * self.cost(cents)                                   -> record spend
  * self.escalate(...)                                 -> pause job for human
"""
from __future__ import annotations
import time, traceback, uuid
from typing import Type, TypeVar, Optional, Dict, Any, List
from pydantic import BaseModel
from .models import (AgentContext, Job, Event, EventType, HumanEscalation,
                     FatalError, RetryableError, QualityGate)
from .bus import get_bus
from .observability import Tracer, current_span
from .llm import llm_call, llm_json
from .guards import get_cost_guard
from .validators import validate_dangerous_content

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    name: str = "base"
    emoji: str = "🤖"
    tier: str = "standard"    # default model tier for this agent

    def __init__(self, deps: Dict[str, Any] = None):
        self._deps = deps or {}
        self.bus = get_bus()
        self.tracer = Tracer()

    # ----- Override this -----
    def run(self, ctx: AgentContext, job: Job) -> Dict[str, Any]:
        raise NotImplementedError

    # ----- Public helpers -----
    def llm(self, prompt: str, *, tier: str = None, system: str = "",
            max_tokens: int = None, temperature: float = 0.7) -> str:
        t = tier or self.tier
        span = current_span()
        with self.tracer.span(f"{self.name}.llm", agent=self.name) as s:
            s.annotate("tier", t)
            text, meta = llm_call(prompt, tier=t, system=system,
                                  max_tokens=max_tokens, temperature=temperature, span=s)
            self._record_cost(meta.get("cost_usd", 0))
            if span:
                span.annotate(f"{self.name}_model", meta.get("model"))
            return text

    def llm_structured(self, prompt: str, *, result_type: Type[T], tier: str = None,
                       system: str = "", retries: int = 2) -> T:
        t = tier or self.tier
        span = current_span()
        with self.tracer.span(f"{self.name}.llm_structured", agent=self.name) as s:
            s.annotate("result_type", result_type.__name__)
            obj = llm_json(prompt, result_type=result_type, tier=t, system=system,
                           retries=retries, span=s)
            s.annotate("ok", True)
            return obj

    def emit(self, message: str, status: str = "info", action: str = "",
             job: Job = None, **data):
        self.bus.agent(self.name, f"{self.emoji} {message}", status, action or self.name,
                       job_id=job.id if job else None, **data)

    def emit_info(self, msg: str, job=None, **kw):    self.emit(msg, "info", "info", job, **kw)
    def emit_ok(self, msg: str, job=None, **kw):      self.emit(msg, "success", "ok", job, **kw)
    def emit_warn(self, msg: str, job=None, **kw):    self.emit(msg, "warn", "warn", job, **kw)
    def emit_err(self, msg: str, job=None, **kw):     self.emit(msg, "error", "error", job, **kw)

    def cost(self, usd: float, detail: str = ""):
        self._record_cost(usd, detail)

    def escalate(self, *, severity: str = "ask", summary: str,
                 options: List[Dict[str,str]] = None, context: dict = None):
        raise HumanEscalation(severity=severity, summary=summary,
                              options=options, context=context)

    def check_safety(self, text: str) -> List[str]:
        return validate_dangerous_content(text)

    # ----- Internal -----
    def _record_cost(self, usd: float, detail: str = ""):
        from . import ledger as _ledger
        try:
            _ledger.record(self.name, cost_usd=usd, detail=detail)
        except Exception:
            pass
        try:
            get_cost_guard().record("global", usd)
        except Exception:
            pass
        try:
            self.bus.cost(self.name, int(usd * 100), detail)
        except Exception:
            pass
