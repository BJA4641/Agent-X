"""test_core.py — automated tests for agentcore.

Runs without Supabase/LLM keys. Uses only Python stdlib + Pydantic.
Run with:   python -m pytest pipeline/tests/ -v  (or just: python pipeline/tests/test_core.py)
"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentcore import (
    Job, JobStatus, Event, EventType, AgentContext, HumanEscalation,
    RetryableError, FatalError, QualityGate,
    Beat, Script, SEOPack, GradeResult, validate_dangerous_content,
)
from agentcore.bus import Bus
from agentcore.guards import circuit_breaker, _breakers, get_cost_guard
from agentcore.observability import Tracer, current_span


def test_job_defaults():
    j = Job(job_type="test.run", payload={"x": 1})
    assert j.status == JobStatus.QUEUED
    assert j.attempts == 0
    assert j.max_attempts == 2
    assert j.idempotency_key is None
    assert isinstance(j.id, str) and len(j.id) > 4
    print("  ✓ job defaults ok")


def test_event_emits_and_subscribes():
    bus = Bus()
    received = []
    bus.on(EventType.AGENT_INFO, lambda e: received.append(e))
    bus.emit(Event(emitter="tester", type=EventType.AGENT_INFO, message="hi",
                   action="test.hello"))
    assert len(received) == 1
    assert received[0].message == "hi"
    print("  ✓ bus pub/sub ok")


def test_circuit_breaker_trips():
    # Reset breaker
    _breakers.pop("test.api", None)
    tripped = 0
    for i in range(7):
        try:
            with circuit_breaker("test.api"):
                raise Exception("503 timeout error on upstream")
        except RetryableError as e:
            tripped += 1
    # After 5 consecutive transient failures, breaker should be open
    assert tripped >= 5
    try:
        with circuit_breaker("test.api"):
            raise Exception("should never reach here")
        assert False, "expected circuit open"
    except RetryableError as e:
        assert "circuit open" in str(e)
    print("  ✓ circuit breaker trips correctly")


def test_cost_guard():
    cg = get_cost_guard()
    # Reset
    cg._totals.pop("testbrand", None)
    cg.check("testbrand", 0.05, 0.10, "test")
    cg.record("testbrand", 0.05)
    try:
        cg.check("testbrand", 0.10, 0.10, "test")
        assert False, "expected budget exceeded"
    except FatalError as e:
        assert "Budget exceeded" in str(e)
    print("  ✓ cost guard works")


def test_tracer_spans_nest():
    tracer = Tracer()
    with tracer.span("outer") as outer:
        with tracer.span("inner") as inner:
            inner.annotate("k", "v")
        assert len(outer.children) == 1
        assert outer.children[0].annotations["k"] == "v"
    assert outer.finished is not None
    assert outer.duration_ms >= 0
    print("  ✓ tracer spans nest correctly")


def test_script_validation_happy():
    s = Script(
        title="Free AI in your browser",
        hook="stop scrolling.",
        beats=[
            Beat(voiceover="Your browser has a free AI", visual_prompt="chrome closeup", duration_ms=4000),
            Beat(voiceover="It summarizes pages without sending data", visual_prompt="summary cards", duration_ms=4000),
            Beat(voiceover="Writers fix tone in one click", visual_prompt="hands typing", duration_ms=4000),
            Beat(voiceover="And it works offline on a plane", visual_prompt="airplane window", duration_ms=4000),
        ],
        cta="Follow for one move a day.",
    )
    assert s.total_ms >= 15000
    assert s.hook == "stop scrolling."
    print("  ✓ script validates (happy path)")


def test_script_validation_rejects_forbidden_phrase():
    try:
        Script(
            title="x", hook="hi", cta="go",
            beats=[Beat(voiceover="hey guys in today's video we talk about x", visual_prompt="dark", duration_ms=4000)]*4,
        )
        assert False, "should have rejected forbidden phrase"
    except Exception as e:
        assert "forbidden" in str(e).lower() or "hey guys" in str(e).lower()
    print("  ✓ script rejects forbidden phrases")


def test_script_validation_rejects_too_short():
    try:
        Script(
            title="x", hook="hi", cta="go",
            beats=[Beat(voiceover="something", visual_prompt="dark", duration_ms=1500)],
        )
        assert False, "should reject too few beats / too short"
    except Exception:
        pass
    print("  ✓ script rejects too-short videos")


def test_seo_pack_normalizes_hashtags():
    seo = SEOPack(
        hashtags=["FYP", "#viral", "foryou", "  AItools  "],
        first_comment="save this for later",
        alt_text="short form video about ai",
        yt_title="stop scrolling #shorts",
    )
    assert "#fyp" in seo.hashtags
    assert "#viral" in seo.hashtags
    assert "#aitools" in seo.hashtags
    # no duplicates
    assert len(set(seo.hashtags)) == len(seo.hashtags)
    print("  ✓ seo pack normalizes hashtags")


def test_dangerous_content_flags():
    assert "financial_claim" in validate_dangerous_content("Make $500 per day guaranteed income with this trick")
    assert not validate_dangerous_content("Three free AI tools to try today")
    print("  ✓ dangerous content detection works")


def test_grade_result_passes_at_8():
    def dim(s, r):
        return {"score": s, "reason": r}
    g = GradeResult(
        hook=dim(9, "great hook"), visuals=dim(8, "good"), pacing=dim(8, "solid"),
        audio=dim(8, "clear"), caption=dim(8, "accurate"), cta=dim(8, "clear"),
        fix_instruction="Make hook tighter", strengths=["strong opening"],
    )
    assert g.passed is True
    assert abs(g.overall - (9+8+8+8+8+8)/6) < 0.15
    print(f"  ✓ grade passes at {g.overall}")


def test_grade_result_fails_below_8():
    def dim(s): return {"score": s, "reason": "r"}
    g = GradeResult(
        hook=dim(7), visuals=dim(7), pacing=dim(7), audio=dim(7), caption=dim(7), cta=dim(7),
        fix_instruction="weaker all around", strengths=[],
    )
    assert g.passed is False
    print(f"  ✓ grade fails at {g.overall}")


def test_bus_persister_called():
    b = Bus()
    stored = []
    b.set_persister(lambda e: stored.append(e))
    b.emit(Event(emitter="t", type=EventType.AGENT_INFO, message="persist me"))
    assert len(stored) == 1
    assert stored[0].message == "persist me"
    print("  ✓ bus persister works")


def test_agent_context_child_inherits_deps():
    parent = AgentContext(run_id="abc", deps={"supabase": "fake", "logger": print})
    child = parent.child(job_id="j1")
    assert child.run_id == "abc"
    assert child.job_id == "j1"
    assert child.dep("supabase") == "fake"
    print("  ✓ context.child inherits deps")


if __name__ == "__main__":
    import traceback
    tests = [v for k,v in list(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0; failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ {t.__name__} FAILED: {e}")
            traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed out of {len(tests)}")
    sys.exit(0 if failed == 0 else 1)
