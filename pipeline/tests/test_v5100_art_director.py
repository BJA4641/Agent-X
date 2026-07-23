"""v5.10.0 — Art Director (REQ-ARTDIRECTOR-1).

The quality gap this closes: the renderer reads `beat.visual_prompt`, and the
writer was putting narration there. Image models were being asked to draw a
sentence instead of a shot.

The invariant that matters most: art direction must NEVER become a new reason
that nothing publishes. This platform already lost its entire output history to
one step that preferred waiting over shipping.
"""
import os, sys, inspect
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from workers.departments import art_director as ad


BEATS = [
    {"voiceover": "Most people scrub their face far too hard."},
    {"voiceover": "A gentle cleanser does more in ten seconds."},
    {"voiceover": "Pat dry — never rub."},
]


# ------------------------------------------------- compose_prompt

def test_compose_builds_a_shot_not_a_sentence():
    p = ad.compose_prompt({"subject": "a ceramic cleanser bottle on wet tile",
                           "composition": "tight close-up",
                           "lighting": "soft window light",
                           "camera": "85mm, shallow depth of field",
                           "style": "editorial photography",
                           "palette": "cream and sage"})
    for frag in ("ceramic cleanser", "close-up", "window light", "85mm", "9:16"):
        assert frag in p


def test_compose_skips_empty_fields_cleanly():
    p = ad.compose_prompt({"subject": "a dog"})
    assert p.startswith("a dog")
    assert ", ," not in p


def test_compose_is_length_bounded():
    p = ad.compose_prompt({"subject": "x" * 5000, "composition": "y" * 5000})
    assert len(p) <= 900


# ------------------------------------------------- deterministic fallback

def test_fallback_covers_every_beat():
    pack = ad.fallback_pack(BEATS, "skincare", "editorial")
    assert len(pack) == len(BEATS)
    assert all(s["subject"] for s in pack)
    assert all(s["source"] == "fallback" for s in pack)


def test_fallback_varies_framing_so_frames_are_not_identical():
    pack = ad.fallback_pack(BEATS, "skincare", "")
    assert len({s["composition"] for s in pack}) == len(BEATS)
    assert len({s["camera"] for s in pack}) == len(BEATS)


def test_fallback_always_carries_a_negative_prompt():
    for s in ad.fallback_pack(BEATS, "t", ""):
        assert "watermark" in s["negative"] and "deformed hands" in s["negative"]


def test_fallback_respects_beat_cap():
    many = [{"voiceover": f"beat {i}"} for i in range(50)]
    assert len(ad.fallback_pack(many, "t", "")) == ad.ART_MAX_BEATS


# ------------------------------------------------- parsing real model output

def test_parses_plain_json():
    txt = '[{"subject":"a dog","composition":"wide","lighting":"soft","camera":"35mm","style":"doc","palette":"warm"}]'
    got = ad._parse_shots(txt, 1)
    assert got and got[0]["subject"] == "a dog" and got[0]["source"] == "llm"


def test_parses_json_inside_code_fences_and_prose():
    txt = 'Sure! Here you go:\n```json\n[{"subject":"a cat"}]\n```\nHope that helps.'
    got = ad._parse_shots(txt, 1)
    assert got and got[0]["subject"] == "a cat"


def test_parse_returns_empty_on_junk_instead_of_raising():
    for junk in ("", "no json here", "{not: valid}", "[[[", None):
        assert ad._parse_shots(junk, 3) == []


def test_parse_supplies_a_negative_when_the_model_omits_one():
    got = ad._parse_shots('[{"subject":"a lamp"}]', 1)
    assert got[0]["negative"], "a missing negative must be back-filled, not left blank"


# ------------------------------------------------- the fail-open invariant

def test_direct_hands_off_to_render_even_when_everything_fails(monkeypatch):
    """THE critical test. Free models down, no DB, junk input — the render job
    must still be spawned. Art direction is never allowed to stall the pipeline."""
    import agentcore.council as council
    monkeypatch.setattr(council, "free_chat",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("all free down")))

    spawned = []

    class _W:
        class queue:
            @staticmethod
            def complete(job, res): spawned.append(("complete", res))
        def spawn(self, jt, payload, **kw):
            spawned.append(("spawn", jt)); return None

    class _Bus:
        def agent(self, *a, **k): pass

    class _Job:
        id = "j1"; account_id = None; project_id = None; brand_id = None; priority = 50
        payload = {"item_id": None, "script": {"beats": list(BEATS)}, "topic": "skincare"}

    class _Ctx:
        deps = {"bus": _Bus(), "supabase": None}

    ad.direct(_W(), _Job(), _Ctx())
    assert ("spawn", "creative.render") in spawned, "render MUST still be queued"
    assert any(k == "complete" for k, _ in spawned)


def test_every_beat_gets_a_visual_prompt_after_direction(monkeypatch):
    import agentcore.council as council
    monkeypatch.setattr(council, "free_chat",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    script = {"beats": [dict(b) for b in BEATS]}

    class _W:
        class queue:
            @staticmethod
            def complete(job, res): pass
        def spawn(self, *a, **k): return None
    class _Bus:
        def agent(self, *a, **k): pass
    class _Job:
        id = "j2"; account_id = None; project_id = None; brand_id = None; priority = 50
        payload = {"item_id": None, "script": script, "topic": "skincare"}
    class _Ctx:
        deps = {"bus": _Bus(), "supabase": None}

    ad.direct(_W(), _Job(), _Ctx())
    for beat in script["beats"]:
        assert beat.get("visual_prompt"), "renderer reads visual_prompt — it must be set"
        assert beat.get("art", {}).get("negative")
    assert script["art_directed"]["shots"] == len(BEATS)


def test_disabled_flag_still_hands_off(monkeypatch):
    monkeypatch.setattr(ad, "ART_DIRECTOR_ENABLED", False)
    spawned = []
    class _W:
        class queue:
            @staticmethod
            def complete(job, res): pass
        def spawn(self, jt, payload, **kw): spawned.append(jt); return None
    class _Bus:
        def agent(self, *a, **k): pass
    class _Job:
        id = "j3"; account_id = None; project_id = None; brand_id = None; priority = 50
        payload = {"item_id": None, "script": {"beats": list(BEATS)}, "topic": "t"}
    class _Ctx:
        deps = {"bus": _Bus(), "supabase": None}
    ad.direct(_W(), _Job(), _Ctx())
    assert "creative.render" in spawned


# ------------------------------------------------- wiring + cost stance

def test_grading_now_routes_through_art_direction():
    from workers.departments import cqo
    src = inspect.getsource(cqo.grade_script)
    assert '"art.direct"' in src
    assert src.index('"art.direct"') < len(src)


def test_art_director_is_free_first():
    src = inspect.getsource(ad)
    assert "free_chat" in src
    for banned in ("force_paid", "anthropic", "llm.chat"):
        assert banned not in src, f"art direction must stay on the free ladder, found {banned!r}"


def test_one_model_call_per_reel_not_per_beat():
    src = inspect.getsource(ad.direct)
    assert src.count("free_chat(") == 1, "one direction call per reel, not per beat"
