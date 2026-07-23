"""agentcore/ratelimit.py — v5.10.1 REQ-RATELIMIT-1.

The problem, measured
---------------------
38 × `HTTP 429 Too Many Requests` from gemini in a six-hour window, on a
SINGLE-THREADED worker. The writer was not being throttled by anything: it
called the free tier as fast as the queue fed it, tripped the per-minute quota,
and every downstream retry hammered the same exhausted provider.

Two consequences:
  1. Today: free capacity collapses in bursts, the writer delays 30 min, and the
     account misses its SLA while a perfectly good provider sits in cooldown.
  2. Tomorrow: REQ-PARALLEL-1 multiplies concurrency by ~8. Without pacing that
     turns an occasional 429 into a permanent one. **This module is a hard
     prerequisite for concurrency** (DEC-029) — it must land first.

Design
------
* Token bucket per provider: a sustained rate plus a small burst allowance.
* Thread-safe by construction (single lock per bucket) so it stays correct when
  the thread pool arrives.
* `acquire()` BLOCKS for a bounded time rather than failing — a 900 ms wait is
  vastly cheaper than a 30-minute retry delay.
* Adaptive: a real 429 halves the effective rate for a cooldown window;
  sustained success restores it. The provider tells us its limit, we listen.
* Fail-open: any internal error means "allow the call". A rate limiter must
  never become the reason nothing ships.
"""
from __future__ import annotations
import os
import threading
import time

# Conservative per-minute defaults for free tiers. Env-tunable per provider.
_DEFAULT_RPM = {
    "gemini": int(os.environ.get("RPM_GEMINI", "10")),
    "groq": int(os.environ.get("RPM_GROQ", "25")),
    "openrouter": int(os.environ.get("RPM_OPENROUTER", "15")),
    "anthropic": int(os.environ.get("RPM_ANTHROPIC", "45")),
    "openai": int(os.environ.get("RPM_OPENAI", "45")),
    "fal": int(os.environ.get("RPM_FAL", "30")),
}
_FALLBACK_RPM = int(os.environ.get("RPM_DEFAULT", "20"))
_MAX_WAIT_S = float(os.environ.get("RATELIMIT_MAX_WAIT_S", "8"))
_PENALTY_S = float(os.environ.get("RATELIMIT_PENALTY_S", "120"))


class TokenBucket:
    """Classic token bucket. capacity = burst, refill = rate per second."""

    def __init__(self, rpm: int, burst: int = None):
        self.rpm = max(1, int(rpm))
        self.capacity = float(burst if burst is not None else max(2, self.rpm // 4))
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self.lock = threading.Lock()
        self.penalty_until = 0.0
        self.hits_429 = 0

    # ---- internals ----
    def _rate_per_s(self, now: float) -> float:
        base = self.rpm / 60.0
        return base / 2.0 if now < self.penalty_until else base

    def _refill(self, now: float):
        elapsed = max(0.0, now - self.updated)
        self.tokens = min(self.capacity, self.tokens + elapsed * self._rate_per_s(now))
        self.updated = now

    # ---- API ----
    def try_take(self) -> bool:
        """Non-blocking. True if a token was available."""
        with self.lock:
            now = time.monotonic()
            self._refill(now)
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    def wait_time(self) -> float:
        """Seconds until the next token, 0 if one is available now."""
        with self.lock:
            now = time.monotonic()
            self._refill(now)
            if self.tokens >= 1.0:
                return 0.0
            deficit = 1.0 - self.tokens
            return deficit / max(1e-6, self._rate_per_s(now))

    def penalise(self):
        """Called on a real 429/rate-limit response: halve the rate for a window."""
        with self.lock:
            self.hits_429 += 1
            self.penalty_until = time.monotonic() + _PENALTY_S
            self.tokens = 0.0

    def recover(self):
        """Called on sustained success — clears the penalty early."""
        with self.lock:
            self.penalty_until = 0.0


_BUCKETS: dict = {}
_REG_LOCK = threading.Lock()


def bucket_for(provider: str) -> TokenBucket:
    key = (provider or "unknown").lower()
    with _REG_LOCK:
        b = _BUCKETS.get(key)
        if b is None:
            b = TokenBucket(_DEFAULT_RPM.get(key, _FALLBACK_RPM))
            _BUCKETS[key] = b
        return b


def acquire(provider: str, max_wait_s: float = None) -> tuple:
    """Block (bounded) until a token is available for `provider`.

    Returns (allowed: bool, waited_s: float). `allowed` is False only when the
    wait would exceed max_wait_s — the caller should then try the NEXT rung of
    the ladder rather than sleeping, which is exactly what free_chat does.

    Fail-open: any internal error returns (True, 0.0).
    """
    try:
        limit = _MAX_WAIT_S if max_wait_s is None else float(max_wait_s)
        b = bucket_for(provider)
        if b.try_take():
            return True, 0.0
        wait = b.wait_time()
        if wait > limit:
            return False, wait
        time.sleep(max(0.0, wait))
        b.try_take()          # best-effort; refilled by now
        return True, wait
    except Exception:
        return True, 0.0      # never block production on the limiter itself


def note_rate_limited(provider: str):
    try:
        bucket_for(provider).penalise()
    except Exception:
        pass


def note_success(provider: str):
    try:
        bucket_for(provider).recover()
    except Exception:
        pass


def snapshot() -> dict:
    """Operator view — written to settings.rate_limits by providers.probe."""
    out = {}
    try:
        now = time.monotonic()
        for name, b in list(_BUCKETS.items()):
            out[name] = {
                "rpm": b.rpm,
                "tokens": round(b.tokens, 2),
                "penalised": bool(now < b.penalty_until),
                "hits_429": b.hits_429,
            }
    except Exception:
        pass
    return out
