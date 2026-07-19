"""memory.py — persistent user/agent conversation per account/project.
The Architect, Strategist, and Brain all load recent memory before they work,
so they remember user feedback, brand changes, and past grades across ticks.
"""
from . import config

MAX_ENTRIES = 40  # how many recent memory items to stuff into prompts


def _sb():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.supabase_service_key())


def add(account_id=None, project_id=None, role="system", content="", metadata=None):
    """Write one memory entry. Does not fail if Supabase is down."""
    if not content: return
    if not config.HAS_SUPABASE: return
    try:
        _sb().table("memory_entries").insert({
            "tenant_id": config.TENANT_ID,
            "account_id": account_id, "project_id": project_id,
            "role": role, "content": content[:2000],
            "metadata": metadata or {},
        }).execute()
    except Exception as e:
        print(f"[memory] write failed: {e}")


def recent(account_id=None, project_id=None, limit=MAX_ENTRIES) -> list:
    """Return recent memory as [{'role','content','created_at'}] for prompt stuffing."""
    if not config.HAS_SUPABASE: return []
    try:
        sb = _sb()
        q = sb.table("memory_entries").select("role,content,created_at,metadata").order("created_at")
        if account_id: q = q.eq("account_id", account_id).limit(limit)
        elif project_id: q = q.eq("project_id", project_id).limit(limit)
        else: q = q.limit(limit)
        return (q.execute().data or [])[-limit:]
    except Exception:
        return []


def context_block(account_id=None, project_id=None) -> str:
    """Return a formatted string to append to prompts with relevant history."""
    entries = recent(account_id, project_id)
    if not entries: return "No prior guidance yet."
    out = []
    for e in entries[-15:]:
        tag = {"user":"FOUNDER","architect":"ARCHITECT","strategist":"STRATEGIST",
               "brain":"WRITER","qa":"QA","grader":"GRADER","visuals":"VISUALS",
               "system":"SYSTEM"}.get(e["role"], e["role"].upper())
        out.append(f"[{tag}] {e['content']}")
    return "\n".join(out)


def load_grade_feedback(account_id=None, project_id=None) -> str:
    """Pull recent failing-grade feedback so future scripts avoid the same mistakes."""
    entries = [e for e in recent(account_id, project_id, limit=20)
               if e["role"] == "grader" and (e.get("metadata") or {}).get("passed") is False]
    if not entries: return ""
    return "\n".join(f"- {e['content']}" for e in entries[-5:])
