"""agentcore/skills.py — v5.8.2 department skill packs.

Each department can carry a SKILL.md playbook (same format as Anthropic's
open Agent Skills): concrete procedures, examples of good output, and
hard rules. The skill is injected into that department's LLM prompts so
agents work from an expert playbook instead of a bare instruction.

Layout (inside the pipeline/ dir so the Dockerfile ships it automatically):

    pipeline/skills/<department>/SKILL.md

Adding more skills: drop any well-rated public SKILL.md (check its license —
MIT/Apache are fine) into a department folder, trim it to the essentials,
and it loads on the next boot. Token cost is real, so files are hard-capped.

Public API:
    load_skill(dept)  -> str  raw skill text ("" if none)
    skill_block(dept) -> str  formatted for prompt injection ("" if none)
"""
from __future__ import annotations
import os

# v5.11.12: raised from 3500. The cap truncates from the START of the file, so
# appending guidance to a skill that already exceeded it did NOTHING and said
# nothing — exactly the workflow ("drop a SKILL.md in") this system advertises.
# Still bounded: every character here is billed on every call that loads it.
_MAX_CHARS = int(os.environ.get("MAX_SKILL_CHARS", "6000"))
_CACHE: dict = {}

_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")


def load_skill(dept: str) -> str:
    dept = (dept or "").strip().lower()
    if not dept:
        return ""
    if dept in _CACHE:
        return _CACHE[dept]
    path = os.path.join(_BASE, dept, "SKILL.md")
    text = ""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            text = raw[:_MAX_CHARS]
            if len(raw) > _MAX_CHARS:
                # Loud, not silent: a truncated skill is guidance the agents
                # never received, and the failure is otherwise invisible.
                _note_truncated(dept, len(raw), _MAX_CHARS)
    except Exception:
        text = ""
    _CACHE[dept] = text
    return text


def skill_block(dept: str) -> str:
    text = load_skill(dept)
    if not text:
        return ""
    return f"\n\n=== EXPERT PLAYBOOK ({dept}) — follow these rules ===\n{text}\n=== END PLAYBOOK ===\n"


def clear_cache():
    _CACHE.clear()


TRUNCATED: dict = {}


def _note_truncated(dept: str, actual: int, cap: int):
    """Record and print truncation so a too-long skill cannot fail quietly."""
    TRUNCATED[dept] = {"chars": actual, "cap": cap, "lost": actual - cap}
    try:
        print(f"[skills] WARNING: {dept}/SKILL.md is {actual} chars, cap is {cap} — "
              f"{actual - cap} chars were NOT sent to the agent. Trim the file or "
              f"raise MAX_SKILL_CHARS.")
    except Exception:
        pass


def health() -> dict:
    """Operator view: which skills load, their size, and what was cut."""
    out = {}
    try:
        for dept in sorted(os.listdir(_BASE)):
            path = os.path.join(_BASE, dept, "SKILL.md")
            if not os.path.exists(path):
                continue
            size = os.path.getsize(path)
            out[dept] = {"chars": size, "truncated": size > _MAX_CHARS,
                         "cap": _MAX_CHARS}
    except Exception:
        pass
    return out
