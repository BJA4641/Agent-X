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
    # v5.11.13 REQ-SKILL-MULTI — a department wears several hats.
    #
    # Until now this loaded exactly ONE file, `<dept>/SKILL.md`. That is why
    # there is a single skill per department: not a design choice, a hardcoded
    # filename. The writer alone needs hook craft, beat structure, humanisation
    # and per-niche voice — four concerns that do not belong in one file, and
    # cannot be swapped or disabled independently when they are.
    #
    # Now: EVERY .md in `<dept>/` loads, alphabetically, sharing the budget.
    # Prefix with a number to control order — 00_hooks.md, 10_beats.md — and
    # SKILL.md keeps working unchanged for anyone who never adds a second file.
    text = ""
    try:
        folder = os.path.join(_BASE, dept)
        files = []
        if os.path.isdir(folder):
            # SKILL.md is the base playbook and always loads FIRST, so a newly
            # added file can never push the foundation out of the budget.
            # Everything else is alphabetical — prefix with digits to order.
            allmd = [fn for fn in os.listdir(folder)
                     if fn.lower().endswith((".md", ".markdown"))]
            base = [fn for fn in allmd if fn.upper() == "SKILL.MD"]
            rest = sorted(fn for fn in allmd if fn.upper() != "SKILL.MD")
            files = base + rest
        elif os.path.exists(os.path.join(_BASE, dept + ".md")):
            files = []
        chunks, used, dropped = [], 0, []
        for fn in files:
            fp = os.path.join(folder, fn)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    raw = f.read().strip()
            except Exception:
                continue
            if not raw:
                continue
            header = f"\n\n--- skill file: {fn} ---\n"
            room = _MAX_CHARS - used - len(header)
            if room <= 200:
                dropped.append(fn)
                continue
            body = raw[:room]
            if len(raw) > room:
                dropped.append(fn)
            chunks.append(header + body)
            used += len(header) + len(body)
        text = "".join(chunks).strip()
        if dropped:
            _note_truncated(dept, used + 1, _MAX_CHARS, dropped)
        if False:
            pass
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


def _note_truncated(dept: str, actual: int, cap: int, files: list = None):
    """Record and print truncation so a too-long skill cannot fail quietly."""
    TRUNCATED[dept] = {"chars": actual, "cap": cap, "lost": max(0, actual - cap),
                       "files_cut": list(files or [])}
    try:
        detail = (" files cut or trimmed: " + ", ".join(files)) if files else ""
        print(f"[skills] WARNING: {dept} skills exceed the {cap}-char budget.{detail} "
              f"Trim them or raise MAX_SKILL_CHARS — cut text never reaches the agent.")
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
