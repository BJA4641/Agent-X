"""v5.8.2 regression tests — council, skills, lessons, no-template-junk.

All offline (providers mocked). Guards the founder mandates:
  * free models draft+debate, Claude never called inside the council
  * writer refuses to fabricate template scripts when allow_demo=False
  * skills load and inject; missing skill degrades to empty string
"""
import os, sys, types
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from agentcore import council, skills


# ------------------------------------------------------------------ council
def test_council_debate_merges_and_never_pays(monkeypatch):
    calls = []
    def fake_call(prov, model, prompt, max_tokens):
        calls.append(prov)
        if "CANDIDATE" in prompt:                       # judge step
            return '{"topics": ["merged best"]}', f"{prov}:{model}"
        return f'{{"topics": ["draft by {prov}"]}}', f"{prov}:{model}"
    monkeypatch.setattr(council, "_providers",
                        lambda: [("groq", "m1"), ("gemini", "m2")])
    monkeypatch.setattr(council, "_call_free", fake_call)
    text, cost, label = council.debate("write topics as JSON")
    assert cost == 0.0
    assert "merged best" in text
    assert "anthropic" not in "".join(calls)            # Claude never in the council
    assert label.startswith("council:")


def test_council_single_provider_degrades_gracefully(monkeypatch):
    monkeypatch.setattr(council, "_providers", lambda: [("groq", "m1")])
    monkeypatch.setattr(council, "_call_free",
                        lambda p, m, pr, mt: ("solo output", f"{p}:{m}"))
    text, cost, label = council.debate("task")
    assert cost == 0.0 and text


def test_council_disabled_env(monkeypatch):
    monkeypatch.setenv("COUNCIL_MODE", "0")
    assert council.enabled() is False


def test_free_chat_rotates_on_failure(monkeypatch):
    def flaky(prov, model, prompt, max_tokens):
        if prov == "groq":
            raise RuntimeError("rate limited")
        return "ok from backup", f"{prov}:{model}"
    monkeypatch.setattr(council, "_providers",
                        lambda: [("groq", "m1"), ("openrouter", "m2")])
    monkeypatch.setattr(council, "_call_free", flaky)
    text, cost, label = council.free_chat("hi")
    assert text == "ok from backup" and cost == 0.0


# ------------------------------------------------------------------ skills
def test_skills_load_and_cap():
    skills.clear_cache()
    s = skills.load_skill("creative")
    assert "3-second" in s or "hook" in s.lower()
    assert len(s) <= 3500
    assert skills.skill_block("creative").startswith("\n\n=== EXPERT PLAYBOOK")


def test_missing_skill_is_empty():
    skills.clear_cache()
    assert skills.load_skill("no_such_dept") == ""
    assert skills.skill_block("no_such_dept") == ""


# ------------------------------------------------------------------ writer honesty
def test_brain_refuses_demo_when_forbidden(monkeypatch):
    """allow_demo=False + no model => RuntimeError, never template junk."""
    from agent import brain, llm as _llm
    monkeypatch.setattr(_llm, "ready", lambda: False)   # no model at all
    with pytest.raises(RuntimeError):
        brain.write_script("test topic", allow_demo=False, verify=False)


def test_brain_verify_false_skips_internal_grader(monkeypatch):
    """verify=False => no internal paid grade loop; grade deferred to cqo."""
    from agent import brain, llm as _llm, ledger as _ledger
    monkeypatch.setattr(_llm, "ready", lambda: True)
    monkeypatch.setattr(_ledger, "budget_ok", lambda *a, **k: True)
    fake_script = ('{"title":"t","hook":"specific surprising hook","beats":'
                   '[{"voiceover":"a","visual_prompt":"cat on desk"},'
                   '{"voiceover":"b","visual_prompt":"cat jumping"},'
                   '{"voiceover":"c","visual_prompt":"cat sleeping"},'
                   '{"voiceover":"d","visual_prompt":"cat eating"}],'
                   '"cta":"follow"}')
    from agentcore import council as _c
    monkeypatch.setattr(_c, "debate_or_chat",
                        lambda prompt, max_tokens=1800: (fake_script, 0.0, "council:test"))
    graded = {"called": False}
    from agent import grader as _g
    monkeypatch.setattr(_g, "grade_post",
                        lambda *a, **k: graded.update(called=True) or {})
    script = brain.write_script("cats", verify=False, allow_demo=False)
    assert script.get("grade", {}).get("deferred_to") == "cqo"
    assert graded["called"] is False                    # single-judge economy holds


def test_free_or_chat_returns_llm_chat_shape(monkeypatch):
    from agentcore import council
    monkeypatch.setattr(council, "enabled", lambda: True)
    monkeypatch.setattr(council, "free_chat", lambda p, max_tokens=800: ("hi", "groq:m1"))
    text, cost, label = council.free_or_chat("prompt")
    assert text == "hi" and cost == 0.0 and label == "council:groq:m1"


def test_new_department_skills_load():
    from agentcore import skills
    skills.clear_cache()
    for dept in ("distribution", "brand_studio", "community", "analytics",
                 "creative", "cqo", "editorial", "research"):
        block = skills.skill_block(dept)
        assert block and len(block) < 4000, dept
    assert "hashtags" in skills.skill_block("distribution").lower()
    assert "hook" in skills.skill_block("creative").lower()
