"""agentcore/memory.py — structured long-term memory, used for cross-run learning.

The legacy agent/memory wrote to a `memory` table; we consolidate on that same
table shape but extend it with `memory.lessons` (typed lessons learned from
post-mortems, per the self-improvement blueprint).
"""
from __future__ import annotations
import time, json, traceback
from typing import List, Dict, Any, Optional
from . import config as _cfg


def _sb():
    return _cfg.supabase()


def add(*, role: str, content: str, account_id=None, project_id=None,
        brand_id=None, metadata: dict = None) -> dict:
    row = {
        "tenant_id": _cfg.TENANT_ID,
        "account_id": str(account_id) if account_id else None,
        "project_id": str(project_id) if project_id else None,
        "brand_id": str(brand_id) if brand_id else None,
        "role": role[:80], "content": content[:4000],
        "metadata": (metadata or {}),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    sb = _sb()
    if sb:
        try:
            res = sb.table("memory").insert(row).execute()
            if res.data:
                return res.data[0]
        except Exception:
            traceback.print_exc()
    return row


def recent(*, role: str = None, account_id=None, limit: int = 10) -> List[Dict[str, Any]]:
    sb = _sb()
    if not sb:
        return []
    try:
        q = sb.table("memory").select("*").eq("tenant_id", _cfg.TENANT_ID).order("created_at", desc=True).limit(limit)
        if role:
            q = q.eq("role", role)
        if account_id:
            q = q.eq("account_id", str(account_id))
        return q.execute().data or []
    except Exception:
        return []


def context_block(account_id=None, project_id=None, limit: int = 6) -> str:
    """Short text block the LLM can drop into a prompt for brand/memory context."""
    sb = _sb()
    if not sb:
        return "(no memory yet)"
    try:
        q = sb.table("memory").select("role,content").order("created_at", desc=True).limit(limit)
        if account_id:
            q = q.eq("account_id", str(account_id))
        rows = q.execute().data or []
        if not rows:
            return "(no memory yet)"
        return "\n".join(f"- [{r['role']}] {str(r.get('content',''))[:300]}" for r in reversed(rows))
    except Exception:
        return "(memory unavailable)"


def load_grade_feedback(account_id=None, project_id=None, limit: int = 4) -> str:
    """Most recent grade-fail notes, so the writer doesn't repeat mistakes."""
    rows = recent(role="grader", account_id=account_id, limit=limit)
    return "\n".join(f"- {str(r.get('content',''))[:200]}" for r in rows) or "(none yet)"


# ---------------- Typed lessons ----------------

def add_lesson(*, scope: str, topic: str, lesson: str, subject_id=None,
               evidence: dict = None, confidence: float = 0.5):
    """Record a lesson learned from a post-mortem (self-improvement loop)."""
    row = {
        "tenant_id": _cfg.TENANT_ID,
        "scope": scope[:40], "subject_id": str(subject_id) if subject_id else "global",
        "topic": topic[:80], "lesson": lesson[:1000],
        "evidence": evidence or {},
        "confidence": max(0.0, min(1.0, float(confidence))),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    sb = _sb()
    if sb:
        try:
            sb.table("lessons").insert(row).execute()
        except Exception:
            traceback.print_exc()
    return row


def lessons_for(*, topic: str = None, scope: str = None, subject_id=None,
                limit: int = 8) -> List[Dict[str, Any]]:
    sb = _sb()
    if not sb:
        return []
    try:
        q = sb.table("lessons").select("*").eq("tenant_id", _cfg.TENANT_ID)
        if topic:
            q = q.eq("topic", topic)
        if scope:
            q = q.eq("scope", scope)
        if subject_id:
            q = q.eq("subject_id", str(subject_id))
        return (q.order("confidence", desc=True).limit(limit).execute().data or [])
    except Exception:
        return []
