"""llm.py — Model Router + typed LLM calls with validation-retry.

Design (from PydanticAI):
  * Every LLM call returns either raw text OR a validated Pydantic object.
  * If structured output fails Pydantic validation, the validation error is fed
    BACK to the model with a request to fix it (up to N retries).
  * Model tier routing: cheap tasks → fast/cheap models; creative/pivotal
    tasks → premium. Central cost routing eliminates per-agent model choice.
  * Circuit breaker per model: if a model is 5xx-ing, trip and fail over.
  * Span for observability (tokens, latency, cost).
"""
from __future__ import annotations
import json, time, traceback
from typing import Type, TypeVar, Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, ValidationError
from .models import RetryableError, FatalError
from .observability import Span
from .guards import circuit_breaker

T = TypeVar("T", bound=BaseModel)

# Tier configuration — model, max tokens, rough $/1k tok (in/out).
# Real costs come from live usage; these are ESTIMATES for the cost-guard pre-check.
TIERS = {
    "cheap":    {"models": ["gemini-2.0-flash", "gpt-4o-mini", "claude-3-5-haiku"],
                 "in_cost": 0.15, "out_cost": 0.60, "max_tokens": 1200},
    "standard": {"models": ["claude-3-5-sonnet-latest", "gpt-4o", "gemini-2.5-pro"],
                 "in_cost": 3.0, "out_cost": 15.0, "max_tokens": 4000},
    "premium":  {"models": ["claude-3-5-opus-latest", "gpt-4o"],
                 "in_cost": 15.0, "out_cost": 75.0, "max_tokens": 8000},
}


class ModelRouter:
    """Picks the best available model per tier.

    In the future, tracks per-model error rates and cost/perf and routes
    dynamically. For now: simple order + circuit breaker fallback.
    """
    def __init__(self, config_fn=None):
        self._config_fn = config_fn   # callable(name) -> value
        self._model_index: Dict[str, int] = {}  # tier -> current model index

    def pick(self, tier: str = "standard") -> str:
        models = TIERS[tier]["models"]
        idx = self._model_index.get(tier, 0)
        return models[idx % len(models)]

    def rotate(self, tier: str):
        """Move to next model in tier (after a failure)."""
        self._model_index[tier] = (self._model_index.get(tier, 0) + 1) % len(TIERS[tier]["models"])


# Global router
_router = ModelRouter()


def get_router() -> ModelRouter:
    return _router


def estimate_cost(tier: str, in_tok: int, out_tok: int) -> float:
    """Return estimated USD cost."""
    t = TIERS[tier]
    return (in_tok * t["in_cost"] + out_tok * t["out_cost"]) / 1_000_000


def llm_call(prompt: str, *, tier: str = "standard", system: str = "",
             max_tokens: int = None, temperature: float = 0.7,
             span: Span = None) -> Tuple[str, Dict[str, Any]]:
    """Call LLM with retry+circuit-breaker+cost tracking.

    Returns (text, meta) where meta has model, tokens_in, tokens_out, cost_usd, latency_s.
    Raises FatalError if all models fail; RetryableError if transient (caller may retry).
    """
    global _router
    from . import config as _cfg
    from . import ledger as _ldgr
    # Lazy import so agentcore doesn't force agent.config import at module load
    t = TIERS[tier]
    max_tok = max_tokens or t["max_tokens"]
    last_err: Exception | None = None
    started = time.time()

    for attempt in range(3):
        model = _router.pick(tier)
        try:
            with circuit_breaker(f"llm.{model}"):
                # Delegate to agent/llm.py (the existing adapter) — but do it here
                # so all LLM flows through one path. agent.llm.chat() currently
                # takes (prompt, max_tokens) and returns (text, cost, label).
                # We prepend any system message to the prompt and use its chosen
                # provider routing (Anthropic → Gemini → Groq → OpenRouter).
                from agent.llm import chat as _chat
                combined = (system + "\n\n" + prompt) if system else prompt
                text, cost_usd, label = _chat(combined, max_tokens=max_tok)
            meta = {
                "model": label or model,
                "tokens_in": 0, "tokens_out": 0,
                "cost_usd": cost_usd,
                "latency_s": time.time() - started,
                "attempt": attempt,
                "tier": tier,
            }
            if span:
                span.annotate("llm_call", meta)
            return text, meta
        except Exception as e:
            last_err = e
            _router.rotate(tier)
            time.sleep(2 ** attempt)
    raise FatalError(f"All LLM attempts failed: {last_err}")


def llm_json(prompt: str, *, result_type: Type[T], tier: str = "standard",
             system: str = "", retries: int = 2, span: Span = None,
             **extra) -> T:
    """Call LLM and return a validated Pydantic object.

    Borrowed directly from PydanticAI: if validation fails, the error is
    fed BACK to the model in a retry prompt, giving it the validation context
    it needs to self-correct. This is the single biggest quality win over
    our old `json.loads(text[text.find('{'):])` approach.
    """
    # Append schema instruction
    schema_hint = result_type.model_json_schema() if hasattr(result_type, "model_json_schema") else {}
    full_prompt = (
        prompt +
        "\n\nReturn STRICT JSON matching this schema (no markdown, no prose, no ```json):\n"
        + json.dumps(schema_hint, indent=2)
    )

    last_err: str = ""
    for attempt in range(retries + 1):
        if last_err:
            retry_prompt = (
                full_prompt +
                f"\n\nYour previous response failed validation with this error:\n{last_err}\n\n"
                "Return ONLY corrected JSON, no explanation."
            )
        else:
            retry_prompt = full_prompt
        text, meta = llm_call(retry_prompt, tier=tier, system=system, span=span)
        # Extract JSON object
        try:
            t = text.strip()
            if "```" in t:
                t = t.split("```")[1]
                if t.startswith("json") or t.startswith("JSON"):
                    t = t[4:]
            start = t.find("{"); end = t.rfind("}")
            if start < 0 or end < 0:
                raise ValueError("no JSON object found")
            obj = json.loads(t[start:end+1])
            parsed = result_type.model_validate(obj)
            if span:
                span.annotate("llm_json", {"validated": True, "attempts": attempt+1, "model": meta["model"]})
            return parsed
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_err = f"{type(e).__name__}: {str(e)[:400]}"
            if span:
                span.annotate("llm_json_retry", {"error": last_err, "attempt": attempt+1})
    raise FatalError(f"Failed to parse/validate {result_type.__name__} after {retries+1} attempts: {last_err}")
