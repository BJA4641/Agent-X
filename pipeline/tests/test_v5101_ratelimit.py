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


# ------------------------------------------------- v5.10.2 concurrency + lanes

def test_lanes_separate_heavy_from_light():
    from agentcore.worker import lane_for
    assert lane_for("creative.render") == "heavy"
    assert lane_for("postprod.finish") == "heavy"
    assert lane_for("creative.write_script") == "light"
    assert lane_for("cqo.grade_script") == "light"
    assert lane_for("art.direct") == "light"
    assert lane_for("paused.prep_cycle") == "free_only"
    assert lane_for("") == "light"


def test_heavy_lane_is_narrow_enough_for_512mb():
    from agentcore.worker import Worker
    from agentcore.jobs import JobQueue
    w = Worker(JobQueue.__new__(JobQueue), name="t")
    assert w._lane_caps["heavy"] <= 2, "wide renders will OOM a 512MB container"
    assert w._lane_caps["light"] >= w._lane_caps["heavy"]


def test_concurrency_defaults_and_rollback_switch(monkeypatch):
    from agentcore.jobs import JobQueue
    import importlib, agentcore.worker as wm
    monkeypatch.setenv("WORKER_CONCURRENCY", "1")
    importlib.reload(wm)
    w = wm.Worker(JobQueue.__new__(JobQueue), name="t")
    assert w.concurrency == 1, "WORKER_CONCURRENCY=1 must restore sequential behaviour"
    monkeypatch.delenv("WORKER_CONCURRENCY", raising=False)
    importlib.reload(wm)


def test_claim_limit_now_uses_concurrency():
    import inspect, agentcore.worker as wm
    src = inspect.getsource(wm.Worker.run_forever)
    assert "limit=self.concurrency" in src
    assert "limit=1)" not in src, "the sequential claim was the throughput ceiling"


def test_breaker_state_is_lock_protected():
    import inspect, agentcore.worker as wm
    src = inspect.getsource(wm.Worker._execute)
    assert "self._state_lock" in src, "shared breaker state must be guarded under threads"


# ------------------------------------------------- REQ-BACKOFF-RESET

def test_ladder_health_gate():
    from workers.departments.sla import ladder_is_healthy
    assert ladder_is_healthy({"usable_count": 7, "below_floor": False}) is True
    assert ladder_is_healthy({"usable_count": 1, "below_floor": False}) is False
    assert ladder_is_healthy({"usable_count": 7, "below_floor": True}) is False
    assert ladder_is_healthy({}) is False
    assert ladder_is_healthy(None) is False


def test_backoff_release_targets_only_no_model_waits():
    import inspect
    from workers.departments import sla
    src = inspect.getsource(sla._release_no_model_backoffs)
    assert '"no model" not in err' in src
    assert "creative.write_script" in src
    assert "ladder_is_healthy" in src


# ------------------------------------------------- v5.10.3 REQ-ESCALATE-2

def test_brain_accepts_force_paid():
    """The gate called write_script(force_paid=True); brain did not accept it,
    so every approved escalation TypeError'd into a free retry. Never again."""
    import inspect
    from agent.brain import write_script
    assert "force_paid" in inspect.signature(write_script).parameters


def test_force_paid_routes_to_the_paid_client_not_the_council():
    import inspect
    from agent import brain
    src = inspect.getsource(brain.write_script)
    i_force = src.index("if force_paid:")
    i_paid = src.index("llm.chat(", i_force)
    i_council_else = src.index("_council.debate(", i_force)
    assert i_paid < i_council_else, "force_paid must bypass the free council"


def test_escalation_no_longer_degrades_to_a_free_retry():
    import inspect
    from workers.departments import creative as cr
    # v5.10.4 moved the write into _do_paid_write; assert on that now.
    src = inspect.getsource(cr._do_paid_write)
    assert "escalate_unsupported" in src
    assert src.count("_brain.write_script(") == 1, \
        "exactly ONE write attempt in the escalation path — the second was the bug"


def test_escalation_still_respects_every_guard():
    from workers.departments.creative import escalation_allowed
    base = dict(free_only=False, daily_remaining=9.0, account_month_remaining=9.0,
                est_cost=0.02, sla_state="behind", produced_today=0, enabled=True)
    assert escalation_allowed(kill_switch_on=True, **base)[0] is False
    assert escalation_allowed(kill_switch_on=False, **{**base, "free_only": True})[0] is False
    assert escalation_allowed(kill_switch_on=False, **{**base, "account_month_remaining": 0.0})[0] is False
    assert escalation_allowed(kill_switch_on=False, **base)[0] is True


# ------------------------------------------------- v5.10.4 REQ-ESC-THROTTLE

def test_escalation_is_serialised_by_default():
    from workers.departments import creative as cr
    assert cr.ESCALATION_CONCURRENCY == 1, \
        "concurrent paid writes race the budget check — default must serialise"


def test_hourly_ceiling_counts_and_expires():
    from workers.departments import creative as cr
    cr._ESC_HIST.clear()
    now = time.time()
    for _ in range(3):
        cr._note_escalation("acct-1", now)
    assert cr.escalations_last_hour("acct-1", now) == 3
    # entries older than an hour fall out of the window
    cr._ESC_HIST["acct-1"] = [now - 4000, now - 3700, now - 10]
    assert cr.escalations_last_hour("acct-1", now) == 1
    cr._ESC_HIST.clear()


def test_ceiling_default_is_survivable_on_a_daily_budget():
    from workers.departments import creative as cr
    worst_case = cr.ESCALATION_MAX_PER_HOUR * cr.ESCALATION_EST_USD
    assert worst_case <= 0.25, \
        "an hour of escalations must not be able to eat a day's budget"


def test_reservation_is_written_before_the_paid_call():
    import inspect
    from workers.departments import creative as cr
    src = inspect.getsource(cr._escalate_to_paid)
    i_reserve = src.index("_reserve_spend(")
    i_call = src.index("_do_paid_write(")
    assert i_reserve < i_call, "money must be committed to the ledger BEFORE it is spent"


def test_budget_is_rechecked_inside_the_lock():
    import inspect
    from workers.departments import creative as cr
    src = inspect.getsource(cr._escalate_to_paid)
    i_lock = src.index("_ESC_SEM.acquire")
    i_recheck = src.index("escalate_raced")
    assert i_lock < i_recheck, "the in-lock re-check is what closes the race"


def test_semaphore_is_always_released():
    import inspect
    from workers.departments import creative as cr
    src = inspect.getsource(cr._escalate_to_paid)
    assert "finally:" in src and "_ESC_SEM.release()" in src, \
        "a leaked semaphore would freeze all future escalations"


def test_ceiling_blocks_before_any_spend_path():
    import inspect
    from workers.departments import creative as cr
    src = inspect.getsource(cr._escalate_to_paid)
    assert src.index("escalate_ceiling") < src.index("_ESC_SEM.acquire")
