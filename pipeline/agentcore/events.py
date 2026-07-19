"""agentcore/events.py — bridge between Bus events and the legacy agent_events
table that the dashboard reads from. Also emits to stdout and to the legacy
`agent.events.emit` so both UIs (v1 feed + v2 job feed) stay lit during
migration.
"""
from __future__ import annotations
import json, os, time, traceback, uuid
from .models import Event, EventType
from . import config as _cfg


AGENT_META = {
    "system":     ("⚙️", "System"),
    "scout":      ("🔭", "Trend Scout"),
    "research":   ("🔎", "Researcher"),
    "architect":  ("🏛️", "Architect"),
    "strategist": ("📋", "Strategist"),
    "planner":    ("📅", "Planner"),
    "brain":      ("✍️", "Script Writer"),
    "visuals":    ("🎨", "Visuals"),
    "voice":      ("🎙️", "Voice"),
    "composer":   ("🎬", "Editor"),
    "qa":         ("🔍", "QA"),
    "cqo":        ("🛡️", "CQO Quality Gate"),
    "grader":     ("🎯", "Grader"),
    "seo":        ("🔖", "SEO"),
    "publisher":  ("📤", "Publisher"),
    "distro":     ("🔁", "Distribution"),
    "analyst":    ("📊", "Analytics"),
    "community":  ("💬", "Community"),
    "cfo":        ("💰", "CFO Budget"),
    "risk":       ("🚨", "Risk"),
    "human_desk": ("👤", "Human Desk"),
    "queue":      ("📥", "Job Queue"),
    "worker":     ("🤖", "Worker"),
    "ceo":        ("👔", "CEO"),
}


def _sb():
    return _cfg.supabase()


def persist_to_agent_events(event: Event):
    """Persist one Bus event to the agent_events table AND stdout."""
    emoji, role = AGENT_META.get(event.emitter, ("•", event.emitter))
    tag = f"[{emoji} {event.emitter}]"
    cost = ""
    if event.cost_cents:
        cost = f"  (${event.cost_cents/100:.4f})"
    print(f"{tag} {event.message}{cost}")

    sb = _sb()
    if not sb:
        return
    row = {
        "id": event.id,
        "tenant_id": _cfg.TENANT_ID,
        "ts": event.ts,
        "emitter": event.emitter,
        "type": event.type.value if isinstance(event.type, EventType) else str(event.type),
        "status": event.status,
        "action": event.action,
        "message": event.message,
        "subject": event.subject or {},
        "job_id": event.job_id,
        "brand_id": str(event.brand_id) if event.brand_id else None,
        "account_id": str(event.account_id) if event.account_id else None,
        "cost_cents": event.cost_cents,
        "data": event.data or {},
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(event.ts)),
    }
    # Map v2 job_id into legacy item_id field so the web sidebar highlights
    if event.data and event.data.get("item_id"):
        row["item_id"] = event.data["item_id"]
    try:
        sb.table("agent_events").insert(row).execute()
    except Exception as e:
        # Don't recursively emit failures; just print
        print(f"[events.persist] insert failed (non-fatal): {e}")


def wire_bus_to_persistence(bus):
    """Attach persister to the global bus. Safe to call multiple times."""
    bus.set_persister(persist_to_agent_events)


def seed_feed_if_empty(bus):
    """Populate a cold feed so the UI looks alive on first boot."""
    sb = _sb()
    if sb:
        try:
            r = sb.table("agent_events").select("id", count="exact").limit(1).execute()
            if r.count and r.count > 0:
                return
        except Exception:
            pass
    seeds = [
        ("system",    "Agent-X v5 worker booted — blueprint online.", "success"),
        ("ceo",       "Standing by. Single active account. Budget hard-capped.", "info"),
        ("cfo",       f"Daily budget ${_cfg.DAILY_BUDGET_USD:.2f}. No infinite retries.", "success"),
        ("cqo",       "Quality gate armed — 8.0/10 min across all six dimensions.", "info"),
        ("scout",     "Loading live trend feeds (Reddit/Google/HN + pattern library).", "info"),
        ("strategist","Reading account playbooks & memory.", "info"),
        ("brain",     "Coffee's poured. Hooks warmed up.", "info"),
        ("composer",  "Render pipeline ready (ffmpeg, edge-tts, Gemini).", "info"),
        ("publisher", "Instagram / YouTube slots mapped — idempotent posting armed.", "info"),
        ("system",    "Idle — first tick fires in ~30s.", "info"),
    ]
    for emitter, msg, status in seeds:
        bus.agent(emitter, msg, status, action="seed")
        time.sleep(0.03)
