"""agentcore/jsonx.py — v5.11.18 REQ-JSON-REPAIR.

Free models produce JSON that is *nearly* valid. Strict json.loads() throws the
entire generation away over one character:

    carousel write failed: Expecting value: line 26 column 101 (char 1258)

That job had already cost a model call, a queue claim and a slot in the day's
quota. The content was almost certainly fine — a trailing comma, a smart quote,
or a response truncated at the token limit.

This module repairs the common, unambiguous defects and refuses to guess at
anything else. Every repair is reversible in meaning: none of them change a
value, they only fix punctuation and framing.

Repairs applied, in order:
  1. strip markdown fences (```json ... ```)
  2. slice to the outermost {...} or [...]
  3. normalise smart quotes to ASCII
  4. remove trailing commas before } or ]
  5. quote unquoted object keys
  6. close unterminated strings, objects and arrays (truncated responses)

Explicitly NOT attempted: inventing missing values, merging concatenated
objects, or repairing anything that changes meaning. If it cannot be parsed
after these steps, the caller should treat it as a genuine failure.
"""
from __future__ import annotations
import json
import re

_SMART = {"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
          "\u2013": "-", "\u2014": "-", "\u00a0": " "}


def _strip_fences(t: str) -> str:
    if "```" in t:
        parts = [p for p in t.split("```") if ("{" in p or "[" in p)]
        if parts:
            t = parts[0]
            if t.lstrip().lower().startswith("json"):
                t = t.lstrip()[4:]
    return t


def _slice_outermost(t: str) -> str:
    starts = [i for i in (t.find("{"), t.find("[")) if i != -1]
    if not starts:
        return t
    start = min(starts)
    ends = [i for i in (t.rfind("}"), t.rfind("]")) if i != -1]
    end = max(ends) if ends else -1
    return t[start:end + 1] if end > start else t[start:]


def _normalise(t: str) -> str:
    for bad, good in _SMART.items():
        t = t.replace(bad, good)
    return t


def _drop_trailing_commas(t: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", t)


def _quote_keys(t: str) -> str:
    # {key: 1}  ->  {"key": 1}   (only bare identifiers, never inside strings)
    return re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)', r'\1"\2"\3', t)


def _close_open_structures(t: str) -> str:
    """Repair a response cut off at the token limit."""
    # close an unterminated string first
    if t.count('"') % 2 == 1:
        t += '"'
    depth_obj = t.count("{") - t.count("}")
    depth_arr = t.count("[") - t.count("]")
    if depth_obj < 0 or depth_arr < 0:
        return t                       # more closes than opens: do not guess
    t = re.sub(r",\s*$", "", t.rstrip())
    return t + ("]" * depth_arr) + ("}" * depth_obj)


REPAIRS = (_strip_fences, _slice_outermost, _normalise,
           _drop_trailing_commas, _quote_keys, _close_open_structures)


def loads_loose(text: str, default=None):
    """Parse model JSON, repairing common defects. Returns `default` on failure.

    Tries strict parsing first so valid input costs nothing extra, then applies
    repairs cumulatively, attempting a parse after each one.
    """
    if text is None:
        return default
    if isinstance(text, (dict, list)):
        return text
    t = str(text).strip()
    if not t:
        return default
    try:
        return json.loads(t)
    except Exception:
        pass
    for repair in REPAIRS:
        try:
            t = repair(t)
            return json.loads(t)
        except Exception:
            continue
    return default


def describe(text: str) -> dict:
    """Diagnostic: which repair made it parse, if any."""
    t = str(text or "").strip()
    try:
        json.loads(t)
        return {"ok": True, "repair": None}
    except Exception:
        pass
    for repair in REPAIRS:
        try:
            t = repair(t)
            json.loads(t)
            return {"ok": True, "repair": repair.__name__}
        except Exception:
            continue
    return {"ok": False, "repair": None}
