"""guards.py — circuit breakers, cost guards, retries.

Production patterns distilled from:
  * Google SRE: circuit breakers on downstream dependencies.
  * CrewAI guardrails: budget caps per task.
  * OpenHands: per-tool retry budgets.
"""
from __future__ import annotations
import time, threading
from collections import defaultdict
from contextlib import contextmanager
from typing import Dict
from .models import FatalError, RetryableError


# ---------------- Circuit breaker ----------------
# Trip a breaker after N failures in a window; stay open for cooldown seconds.
class _Breaker:
    __slots__ = ("failures", "last_fail", "state", "cooldown", "threshold", "window")
    def __init__(self, threshold: int = 5, window_s: float = 60, cooldown_s: float = 30):
        self.failures = 0
        self.last_fail = 0.0
        self.state = "closed"   # closed | open | half-open
        self.cooldown = cooldown_s
        self.threshold = threshold
        self.window = window_s


_breakers: Dict[str, _Breaker] = {}
_breakers_lock = threading.Lock()


def _get(name: str) -> _Breaker:
    with _breakers_lock:
        return _breakers.setdefault(name, _Breaker())


def reset_breaker(name: str):
    with _breakers_lock:
        if name in _breakers:
            del _breakers[name]


@contextmanager
def circuit_breaker(name: str):
    """Usage:
           with circuit_breaker("llm.gpt-4o"):
               call_api()
       Raises RetryableError when open; callers fall over to next model.
    """
    b = _get(name)
    now = time.time()
    if b.state == "open":
        if now - b.last_fail >= b.cooldown:
            b.state = "half-open"
        else:
            raise RetryableError(f"circuit open: {name} (cooldown {int(b.cooldown - (now-b.last_fail))}s)", delay_s=b.cooldown)
    try:
        yield
        # Success: reset if half-open, just stay closed
        with _breakers_lock:
            b.state = "closed"
            b.failures = 0
    except Exception as e:
        # Only count known-transient errors as breaker trips
        msg = str(e).lower()
        transient = any(s in msg for s in ("timeout", "429", "rate limit", "500", "502", "503", "connection", "reset"))
        if transient:
            with _breakers_lock:
                # Reset counter outside window
                if now - b.last_fail > b.window:
                    b.failures = 0
                b.failures += 1
                b.last_fail = now
                if b.failures >= b.threshold:
                    b.state = "open"
            raise RetryableError(str(e), delay_s=min(30, 2**b.failures))
        raise


def handle_circuit_open(fn):
    """Decorator: if circuit_breaker fires inside fn, rotate router and retry 1x."""
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except RetryableError:
            # Let caller handle rotation (ModelRouter level)
            raise
    return wrapper


# ---------------- Cost guard ----------------
# Prevents a single LLM/render job from exceeding its budget.

class CostGuard:
    def __init__(self):
        self._totals: Dict[str, float] = defaultdict(float)   # key -> USD spent today

    def check(self, key: str, est_cost: float, budget: float, label: str = ""):
        """Raise FatalError if adding est_cost to key's total would exceed budget."""
        spent = self._totals.get(key, 0.0)
        if spent + est_cost > budget:
            raise FatalError(f"Budget exceeded for {label or key}: spent ${spent:.4f} + est ${est_cost:.4f} > ${budget:.4f}")

    def record(self, key: str, cost: float):
        self._totals[key] += cost

    def spent(self, key: str) -> float:
        return self._totals.get(key, 0.0)


_cost_guard = CostGuard()


def get_cost_guard() -> CostGuard:
    return _cost_guard


@contextmanager
def cost_guard(key: str, est_cost: float, budget: float, label: str = ""):
    _cost_guard.check(key, est_cost, budget, label)
    yield
