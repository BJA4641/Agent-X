"""v5.10.1 — REQ-RATELIMIT-1 token bucket + REQ-VERSION-2 image version file.

Measured problem: 38 x HTTP 429 from gemini in six hours on a SINGLE-THREADED
worker. Nothing paced the free tier, so the writer burst through the per-minute
quota, then delayed 30 minutes while a healthy provider sat in cooldown.

This module is also a hard prerequisite for REQ-PARALLEL-1: ~8 threads against
an unpaced free tier turns an occasional 429 into a permanent one.
"""
import os, sys, time, inspect, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agentcore import ratelimit as rl


@pytest.fixture(autouse=True)
def _clean_buckets():
    rl._BUCKETS.clear()
    yield
    rl._BUCKETS.clear()


# ------------------------------------------------- token bucket mechanics

def test_burst_is_allowed_then_throttled():
    b = rl.TokenBucket(rpm=60, burst=3)
    assert [b.try_take() for _ in range(3)] == [True, True, True]
    assert b.try_take() is False, "burst must be finite"


def test_tokens_refill_over_time():
    b = rl.TokenBucket(rpm=60, burst=1)     # 1 token/second
    assert b.try_take() is True
    assert b.try_take() is False
    b.updated -= 1.1                        # simulate 1.1s passing
    assert b.try_take() is True


def test_wait_time_is_zero_when_tokens_available():
    b = rl.TokenBucket(rpm=60, burst=2)
    assert b.wait_time() == 0.0


def test_wait_time_is_positive_when_dry():
    b = rl.TokenBucket(rpm=60, burst=1)
    b.try_take()
    assert 0 < b.wait_time() <= 1.5


def test_capacity_never_exceeded_by_long_idle():
    b = rl.TokenBucket(rpm=600, burst=5)
    b.updated -= 3600                        # idle an hour
    b._refill(time.monotonic())
    assert b.tokens <= b.capacity


# ------------------------------------------------- adaptive 429 response

def test_429_halves_the_rate_and_empties_the_bucket():
    b = rl.TokenBucket(rpm=60, burst=5)
    before = b._rate_per_s(time.monotonic())
    b.penalise()
    after = b._rate_per_s(time.monotonic())
    assert after == pytest.approx(before / 2)
    assert b.tokens == 0.0
    assert b.hits_429 == 1


def test_success_clears_the_penalty():
    b = rl.TokenBucket(rpm=60)
    b.penalise()
    assert b.penalty_until > time.monotonic()
    b.recover()
    assert b.penalty_until == 0.0


def test_note_helpers_are_safe_on_unknown_providers():
    rl.note_rate_limited("never-heard-of-it")
    rl.note_success("never-heard-of-it")
    assert "never-heard-of-it" in rl._BUCKETS


# ------------------------------------------------- acquire() contract

def test_acquire_returns_immediately_when_tokens_exist():
    ok, waited = rl.acquire("gemini")
    assert ok is True and waited == 0.0


def test_acquire_declines_rather_than_sleeping_too_long():
    b = rl.bucket_for("gemini")
    b.rpm = 1                # 1/min -> ~60s for the next token
    b.tokens = 0.0
    b.capacity = 1.0
    ok, waited = rl.acquire("gemini", max_wait_s=0.05)
    assert ok is False and waited > 0.05, "must skip to the next rung, not block"


def test_acquire_fails_open_on_internal_error(monkeypatch):
    """A rate limiter must never be the reason nothing ships."""
    monkeypatch.setattr(rl, "bucket_for", lambda p: (_ for _ in ()).throw(RuntimeError("boom")))
    ok, waited = rl.acquire("gemini")
    assert ok is True and waited == 0.0


# ------------------------------------------------- thread safety (REQ-PARALLEL-1 prerequisite)

def test_bucket_is_thread_safe_under_contention():
    b = rl.TokenBucket(rpm=6000, burst=200)
    taken = []
    lock = threading.Lock()

    def worker():
        got = 0
        for _ in range(100):
            if b.try_take():
                got += 1
        with lock:
            taken.append(got)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    total = sum(taken)
    assert total <= 200 + 50, "8 threads must not over-draw the bucket"
    assert total > 0


def test_bucket_registry_is_shared_per_provider():
    assert rl.bucket_for("gemini") is rl.bucket_for("GEMINI")


# ------------------------------------------------- wiring into the ladder

def test_council_paces_and_skips_busy_rungs():
    import agentcore.council as c
    src = inspect.getsource(c.free_chat)
    assert "ratelimit" in src and "skipped to next rung" in src
    assert "note_rate_limited" in src, "a real 429 must feed back into the bucket"
    assert "note_success" in src


def test_429_detection_covers_common_phrasings():
    import agentcore.council as c
    src = inspect.getsource(c.free_chat)
    assert '"429" in msg' in src
    assert "too many requests" in src.lower()


def test_snapshot_shape_for_operators():
    rl.bucket_for("gemini").penalise()
    snap = rl.snapshot()
    assert "gemini" in snap
    for field in ("rpm", "tokens", "penalised", "hits_429"):
        assert field in snap["gemini"]


# ------------------------------------------------- REQ-VERSION-2

def test_version_file_reaches_the_worker_image():
    """The Dockerfile must copy the canonical version file, or agentcore.version
    silently falls back and the dashboard reports a stale version forever."""
    here = os.path.dirname(os.path.abspath(__file__))
    dockerfile = os.path.normpath(os.path.join(here, "..", "Dockerfile"))
    body = open(dockerfile).read()
    assert "web/version.json" in body and "./version.json" in body


def test_fallback_is_a_marker_not_a_plausible_version():
    from agentcore import version as v
    assert not v._FALLBACK[0].isdigit(), \
        "a stale numeric fallback is indistinguishable from a real version"
