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


# ------------------------------------------------- v5.10.7

def test_ledger_records_paid_cost_once():
    import inspect
    from agent import brain
    src = inspect.getsource(brain.write_script)
    assert "REQ-LEDGER-DEDUPE" in src
    assert "_already" in src and "0.0 if _already else cost" in src


def test_backpressure_pauses_production_when_drafts_pile_up():
    from workers.departments import portfolio as pf
    assert pf.MAX_AWAITING_APPROVAL == 5
    src = inspect.getsource(pf.tick)
    i_wait = src.index("awaiting_approval(")
    i_need = src.index("need = max(0,")
    assert i_wait < i_need, "backpressure must be checked BEFORE demand is computed"
    assert "continue" in src[i_wait:i_need + 400]


def test_awaiting_approval_counts_only_drafted():
    import inspect
    from workers.departments import portfolio as pf
    src = inspect.getsource(pf.awaiting_approval)
    assert '"drafted"' in src
    for other in ('"idea"', '"approved"', '"published"'):
        assert other not in src


def test_awaiting_approval_fails_safe_to_zero():
    from workers.departments import portfolio as pf
    assert pf.awaiting_approval(None) == 0


# ------------------------------------------------- v5.10.8 REQ-CHEAP-TEXT

def test_text_defaults_to_the_cheap_tier():
    """100% of the first day's paid spend went to TEXT on a premium reasoning
    model — $1.46 on 50 sonnet script writes — while $0.00 reached images,
    voice or video. Text is a commodity; the money must follow the content."""
    import inspect
    from agent import llm
    src = inspect.getsource(llm.chat)
    assert 'TEXT_TIER_DEFAULT", "cheap"' in src
    assert 'tier = "cheap" if chosen' not in src, "old provider-derived tier must be gone"


def test_chat_accepts_an_explicit_tier():
    import inspect
    from agent import llm
    assert "tier" in inspect.signature(llm.chat).parameters


def test_escalated_write_requests_cheap_tier():
    import inspect
    from agent import brain
    src = inspect.getsource(brain.write_script)
    i = src.index("if force_paid:")
    j = src.index("elif config.get(\"ALLOW_PAID_WRITER\")")
    branch = src[i:j]
    assert "tier=" in branch and '"cheap"' in branch, "escalated write must request the cheap tier"


def test_grader_is_not_pinned_to_a_premium_model():
    import inspect
    from agent import grader
    src = inspect.getsource(grader)
    assert 'model="claude-sonnet-4-5"' not in src, "grading must not hard-pin a premium model"
    assert 'GRADER_TIER' in src


# ------------------------------------------------- v5.11.5 REQ-TOPIC-DEDUPE

def test_topic_normalisation_ignores_case_punctuation_emoji():
    from workers.departments.editorial import _norm_topic
    a = _norm_topic("Black Spots Gone Instantly!")
    b = _norm_topic("black spots gone instantly")
    assert a == b
    c = _norm_topic("Who else has a VERY particular bed time routine? 🧖🏾‍♀️💕✨")
    d = _norm_topic("who else has a very particular bed time routine")
    assert c == d


def test_duplicates_dropped_within_one_batch():
    """5 drafts of 'Black Spots Gone Instantly!' reached the approval queue —
    each a separate paid write and grade for the same idea."""
    from workers.departments.editorial import _drop_recent_duplicates
    out = _drop_recent_duplicates(None, "acct", [
        ("Black Spots Gone Instantly!", "t"),
        ("black spots gone instantly", "t"),
        ("BLACK SPOTS GONE INSTANTLY", "t"),
        ("A Genuinely New Topic", "t"),
    ])
    assert [t for t, _ in out] == ["Black Spots Gone Instantly!", "A Genuinely New Topic"]


def test_dedupe_is_fail_safe_without_a_database():
    from workers.departments.editorial import recent_topics, _drop_recent_duplicates
    assert recent_topics(None, "acct") == set()
    assert len(_drop_recent_duplicates(None, "acct", [("x", "t")])) == 1


def test_dedupe_runs_before_planning_spends_money():
    import inspect
    from workers.departments import editorial as ed
    src = inspect.getsource(ed.ideate)
    assert src.index("_drop_recent_duplicates") < src.index("for topic, bucket in topics")


# ------------------------------------------------- v5.11.6

def test_approval_routes_through_the_art_director():
    """The Art Director shipped in v5.10.0 and never ran once: the approve path
    spawned creative.render directly, skipping art.direct entirely."""
    import inspect
    from workers.departments import human_desk as hd
    src = inspect.getsource(hd)
    assert '"art.direct"' in src
    i_art = src.index('"art.direct"')
    seg = src[max(0, i_art - 1200):i_art]
    assert 'approved' in seg


def test_render_has_a_crashloop_guard_before_heavy_work():
    import inspect
    from workers.departments import creative as cr
    src = inspect.getsource(cr.render)
    assert "_render_attempt_guard" in src
    assert src.index("_render_attempt_guard") < src.index("narration")


def test_quarantine_threshold_is_small():
    from workers.departments import creative as cr
    assert cr.RENDER_MAX_CRASHES <= 3, "a crash-looping render must stop quickly"


def test_voice_is_not_rebilled_on_retry():
    import inspect
    from workers.departments import creative as cr
    src = inspect.getsource(cr.render)
    assert "voice_cached" in src and "os.path.getsize(audio)" in src


# ------------------------------------------------- v5.11.8 REQ-SCOUT-TITLES

def test_borrowed_captions_are_detected():
    from workers.departments.editorial import _looks_borrowed
    assert _looks_borrowed("Can Salish do her skincare in 1 minute?") is True
    assert _looks_borrowed("Get unready with me in the Bahamas!") is True


def test_real_topics_are_not_flagged():
    """'i ' must not match inside 'ai ' — word boundaries required."""
    from workers.departments.editorial import _looks_borrowed
    assert _looks_borrowed("7 AI Pet Gadgets That Save Time") is False
    assert _looks_borrowed("Why AI-Powered Pet Training Apps Are Making Your Dog More Anxious") is False


def test_personal_scaffolding_is_stripped():
    from workers.departments.editorial import _strip_personal, _looks_borrowed
    out = _strip_personal("Can Salish do her skincare in 1 minute?")
    assert "Salish" not in out and "her" not in out.split()
    assert "skincare" in out
    assert _looks_borrowed(out) is False


def test_angle_never_raises_and_passes_clean_titles_through():
    from workers.departments.editorial import angle_from_trend
    clean = "7 AI Pet Gadgets That Save Time"
    assert angle_from_trend(clean, "pets") == clean
    assert angle_from_trend("", "pets") == ""
    assert isinstance(angle_from_trend("Get ready with me!!! 🧖🏾‍♀️", "beauty"), str)


def test_picker_routes_trend_titles_through_the_rewriter():
    import inspect
    from workers.departments import editorial as ed
    src = inspect.getsource(ed._pick_topics)
    assert 'topics.append((title[:120], "trend"))' not in src, \
        "raw scraped titles must never become topics"
    assert "angle_from_trend" in src


def test_writer_prompt_carries_the_grading_rubric():
    """Three consecutive scripts scored 6.0/5.7/6.0 against an 8.0 floor because
    the writer was never shown the rubric it is judged against."""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.normpath(os.path.join(here, "..", "..", "prompts", "script_v3.md"))
    body = open(p, encoding="utf-8").read()
    assert "HOW THIS SCRIPT WILL BE GRADED" in body
    for axis in ("hook", "visuals", "pacing", "audio", "caption", "cta"):
        assert axis in body


# ------------------------------------------------- v5.11.9 REQ-VISUALS-REAL

def test_free_keyless_image_rung_runs_before_the_gradient():
    """All three published reels were plain gradients: aisuite failed (fal
    timeout), gemini 429'd, and the procedural fallback ran silently 16 times."""
    import inspect
    from agent import visuals
    src = inspect.getsource(visuals)
    i_free = src.index("pollinations-free")
    i_grad = src.index('model="rich-gradient-v2"')
    assert i_free < i_grad, "the free keyless generator must be tried before giving up"


def test_gradient_fallback_is_no_longer_silent():
    import inspect
    from agent import visuals
    src = inspect.getsource(visuals)
    assert "NO IMAGE GENERATED" in src
    assert "_note_gradient_fallback" in src
    assert "ok=False" in src.split('model="rich-gradient-v2"')[0][-200:]


def test_art_director_demands_a_photographable_subject():
    import inspect
    from workers.departments import art_director as ad
    src = inspect.getsource(ad._brief)
    assert "photographable" in src.lower()
    assert "NEVER an abstract concept" in src


def test_niche_subjects_are_concrete_scenes():
    from workers.departments.art_director import _subject_bank
    pets = _subject_bank("puppy parenting")
    assert any("puppy" in s for s in pets)
    assert all(len(s) > 15 for s in pets), "a subject must be a scene, not a word"
    skin = _subject_bank("glow up daily skincare")
    assert any("serum" in s or "skin" in s for s in skin)


def test_fallback_never_uses_narration_as_the_image_subject():
    from workers.departments.art_director import fallback_pack
    beats = [{"voiceover": "Most smart feeders starve puppies."}]
    pack = fallback_pack(beats, "puppy gadgets", "", niche_hint="pets")
    assert "starve" not in pack[0]["subject"], "narration must never be the image prompt"
    assert "puppy" in pack[0]["subject"]


# ------------------------------------------------- v5.11.10

def test_worker_beats_from_the_claim_loop():
    """Liveness had two failure-prone signals (a job and a thread). On
    2026-07-24 the worker wrote a provider report at 02:12 while worker_health
    was frozen at 01:46 and heartbeat_pulse was NULL — a working worker showing
    a 29-minute-dead banner."""
    import inspect
    from agentcore.worker import Worker
    src = inspect.getsource(Worker.run_forever)
    assert "self._beat()" in src
    assert src.index("self._beat()") < src.index("self.queue.claim")


def test_beat_is_rate_limited_and_never_raises():
    import inspect
    from agentcore.worker import Worker
    src = inspect.getsource(Worker._beat)
    assert "min_interval_s" in src
    assert "except Exception" in src and "pass" in src


def test_version_hint_resolves():
    from workers.departments.ops import VERSION_HINT
    v = VERSION_HINT()
    assert v and v != "unknown" and v[0].isdigit()


def test_motion_surface_is_smaller_than_the_old_default():
    """zoompan buffered a 1296x2304 surface — over a gigabyte of working set for
    one beat in a 512MB container."""
    from agent.composer import MOTION_W, MOTION_H, ZOOM_FPS
    assert MOTION_W * MOTION_H < 1296 * 2304
    assert ZOOM_FPS <= 30


def test_ffmpeg_thread_count_is_capped():
    import inspect
    from agent import composer
    src = inspect.getsource(composer._run)
    assert "-threads" in src, "each ffmpeg thread allocates its own frame buffers"


# ------------------------------------------------- v5.11.11 REQ-CONTENT-MIX

def test_daily_mix_matches_the_founders_spec():
    """3 reels for one account, 0 for the other, 0 carousels, 0 stories —
    because ideation only ever spawned the reel path."""
    from workers.departments.portfolio import DAILY_FORMAT_MIX
    assert DAILY_FORMAT_MIX["reel"] >= 1
    assert DAILY_FORMAT_MIX["carousel"] >= 1
    assert DAILY_FORMAT_MIX["story"] >= 5


def test_formats_needed_subtracts_what_exists():
    from workers.departments.portfolio import formats_needed
    assert formats_needed(None, "a", produced={}) == {"reel": 1, "carousel": 1, "story": 5}
    assert "reel" not in formats_needed(None, "a", produced={"reel": 3})
    assert formats_needed(None, "a", produced={"reel": 1, "carousel": 1, "story": 5}) == {}


def test_every_format_has_a_handler():
    from workers.departments.portfolio import DAILY_FORMAT_MIX, FORMAT_JOB
    from workers.departments import register_all
    class _W:
        def __init__(self): self.h = {}
        def register(self, t, f): self.h[t] = f
    w = _W(); register_all(w)
    for fmt in DAILY_FORMAT_MIX:
        assert FORMAT_JOB[fmt] in w.h, f"{fmt} has no handler"


def test_story_path_is_light_and_free():
    """A story must never enter the heavy lane or escalate to a paid model —
    its whole purpose is cheap daily volume."""
    import inspect
    from agentcore.worker import lane_for
    from workers.departments import creative as cr
    assert lane_for("creative.write_story") == "light"
    src = inspect.getsource(cr.write_story)
    assert "free_chat" in src
    # check for CALLS, not prose — the docstring legitimately says "never escalate"
    for banned in ("force_paid=", "llm.chat(", "_escalate_to_paid("):
        assert banned not in src, f"story path must stay free, found {banned!r}"


def test_mix_is_spawned_before_the_reel_path():
    import inspect
    from workers.departments import portfolio as pf
    src = inspect.getsource(pf.tick)
    assert src.index("formats_needed(") < src.index("need = max(0, target")


# ------------------------------------------------- v5.11.12 skills + human axis

def test_skills_load_completely_and_report_truncation():
    """The cap truncates from the START of a file, so appending guidance to an
    over-cap skill silently did nothing — the exact 'drop a SKILL.md in'
    workflow this system advertises."""
    from agentcore import skills
    skills.clear_cache()
    for dept in ("creative", "cqo"):
        body = skills.load_skill(dept)
        assert body, f"{dept} skill did not load"
    # Truncation is allowed — it must simply never be SILENT.
    if skills.TRUNCATED:
        for dept, info in skills.TRUNCATED.items():
            assert info.get("files_cut"), f"{dept} truncated without naming the files"


def test_truncation_is_recorded_not_silent():
    import inspect
    from agentcore import skills
    src = inspect.getsource(skills.load_skill)
    assert "_note_truncated" in src
    assert callable(skills.health)


def test_writer_skill_covers_hooks_and_beats():
    from agentcore import skills
    skills.clear_cache()
    body = skills.load_skill("creative").lower()
    assert "hook craft" in body and "beat structure" in body
    assert "max 8 words" in body
    assert "never repeat the hook at the end" in body   # REQ-DUP-HOOK guidance


def test_grader_has_a_human_sounding_axis():
    """Six axes could all pass while the script still read as machine-written."""
    from agentcore import skills
    skills.clear_cache()
    assert "human" in skills.load_skill("cqo").lower()
    import inspect
    from agent import grader
    assert '"human": int' in inspect.getsource(grader) or '"human"' in inspect.getsource(grader)


def test_human_axis_is_enforced_by_the_min_dimension_guard():
    import inspect
    from workers.departments import cqo
    src = inspect.getsource(cqo.grade_script)
    assert '"human"' in src, "a new axis that is not enforced is decoration"


# ------------------------------------------------- v5.11.13

def test_multiple_skill_files_load_per_department():
    """One file per department was a hardcoded filename, not a design choice."""
    from agentcore import skills
    skills.clear_cache()
    body = skills.load_skill("creative")
    assert body.count("--- skill file:") >= 2


def test_base_playbook_loads_first():
    """A newly added file must never push the foundation out of the budget."""
    import re
    from agentcore import skills
    skills.clear_cache()
    names = re.findall(r"--- skill file: (\S+)", skills.load_skill("creative"))
    assert names and names[0].upper() == "SKILL.MD"


def test_scorecard_reports_zero_pass_rate_honestly():
    from workers.departments.scorecard import compute
    out = compute(
        rows_grades=[{"action": "cqo_fail", "overall": 6.0}] * 18,
        rows_board=[{"status": "rejected"}] * 13 + [{"status": "published"}] * 3,
        rows_events=[{"agent": "queue", "status": "info"}] * 100
                    + [{"agent": "composer", "status": "info"}] * 2,
        spend_usd=1.865)
    assert out["pass_rate_pct"] == 0.0
    assert out["rewrites_per_pass"] is None       # never divide by a zero pass count
    assert out["overhead_ratio_pct"] > 90
    assert out["cost_per_approved_usd"] is not None


def test_verdict_will_say_flat_when_nothing_moves():
    """A scorecard that always shows progress measures nothing."""
    from workers.departments.scorecard import verdict
    same = {"pass_rate_pct": 0.0, "avg_grade": 6.0}
    assert verdict(same, same)["trend"] == "flat"
    assert verdict(same, None)["trend"] == "first_measurement"


def test_verdict_detects_regression():
    from workers.departments.scorecard import verdict
    prev = {"pass_rate_pct": 40.0, "cost_per_approved_usd": 0.10}
    now = {"pass_rate_pct": 10.0, "cost_per_approved_usd": 0.40}
    assert verdict(now, prev)["trend"] == "regressing"


def test_scorecard_handler_registered():
    from workers.departments import register_all
    class _W:
        def __init__(self): self.h = {}
        def register(self, t, f): self.h[t] = f
    w = _W(); register_all(w)
    assert "ops.scorecard" in w.h
