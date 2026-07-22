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

_MAX_CHARS = 3500          # hard cap per skill — tokens cost money
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
                text = f.read()[:_MAX_CHARS]
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
