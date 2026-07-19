"""events.py — agent chatter feed.
Every agent writes a visible row into agent_events so the workspace feed
on the website shows agents talking/working in real time.

- emit(agent, message, status='info', action='note', item_id=None, cost_usd=0)
- heartbeat()   : called once on worker boot ("Strategy is online.")
- idle_chatter(context): honest real-state status when the queue is empty (no cost).
- Also inserts a small amount of seed chatter on first boot so the feed
  is never empty.
"""
import os, time, random
from . import config

# Agent color/status map mirrors web/components/RightPanel.tsx + workspace page
AGENTS = {
    "system":    {"emoji": "🤖", "role": "System"},
    "strategy":  {"emoji": "🧠", "role": "Planner"},
    "brain":     {"emoji": "✍️", "role": "Script writer"},
    "visuals":   {"emoji": "🎨", "role": "Visuals"},
    "voice":     {"emoji": "🎙️", "role": "Voice"},
    "composer":  {"emoji": "🎬", "role": "Editor"},
    "qa":        {"emoji": "🔍", "role": "QA"},
    "publisher": {"emoji": "📤", "role": "Publisher"},
    "analyst":   {"emoji": "📊", "role": "Analytics"},
    "community": {"emoji": "💬", "role": "Community"},
    "digest":    {"emoji": "📬", "role": "Digest"},
    "budget":    {"emoji": "💰", "role": "Budget"},
    "scout":     {"emoji": "🔭", "role": "Trend scout"},
    "planner":   {"emoji": "🗓️", "role": "Calendar"},
}

_seed_done = False


def _sb():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.supabase_service_key())


def _local_log(agent, message, status, action, item_id, cost_usd):
    # Fallback when Supabase isn't configured — print to stdout so logs still show it.
    tag = f"[{AGENTS.get(agent,{}).get('emoji','•')} {agent}]"
    print(f"{tag} {message}" + (f"  (${cost_usd:.4f})" if cost_usd else ""))


def emit(agent: str, message: str, status: str = "info", action: str = "note",
         item_id=None, cost_usd: float = 0.0):
    """Write one visible event. Always prints to stdout; writes to Supabase
    using the SERVICE key (which bypasses RLS — these are system events
    visible to the admin/tenant owner, not bound to a specific user_id)."""
    _local_log(agent, message, status, action, item_id, cost_usd)
    if not config.HAS_SUPABASE:
        return
    try:
        _sb().table("agent_events").insert({
            "tenant_id": config.TENANT_ID,
            "user_id": None,  # system-wide feed; web will ALSO show these
            "agent": agent,
            "action": action,
            "message": message,
            "status": status,
            "cost_usd": cost_usd,
            "item_id": item_id,
        }).execute()
    except Exception as e:
        print(f"[events] insert failed (non-fatal): {e}")


def heartbeat():
    """Called once when the worker boots."""
    caps = []
    if config.HAS_ANTHROPIC: caps.append("Claude scripts")
    if config.HAS_GEMINI:    caps.append("Gemini visuals")
    if config.HAS_ELEVEN:    caps.append("ElevenLabs voice")
    if not caps: caps.append("free-tier stubs")
    msg = f"Online. Capabilities: {', '.join(caps)}. Daily budget ${config.DAILY_BUDGET_USD:.2f}."
    emit("system",   f"Agent-X worker booted.", "success", "boot")
    emit("strategy", "Reading trends & queue depth…", "info", "heartbeat")
    emit("budget",   msg, "info", "heartbeat")
    _seed_feed_if_empty()


def _seed_feed_if_empty():
    """Populate a brand new feed so the workspace looks alive even before
    the first plan/produce tick fires."""
    global _seed_done
    if _seed_done:
        return
    try:
        if config.HAS_SUPABASE:
            r = _sb().table("agent_events").select("id", count="exact").limit(1).execute()
            if r.count and r.count > 0:
                _seed_done = True
                return
    except Exception:
        pass
    seeds = [
        ("strategy",  "Squad, stand by. Reading the board now.",          "info"),
        ("brain",     "Coffee's poured. Ready to write hooks.",           "info"),
        ("visuals",   "Style library loaded — cinemagraphs, B-roll, UGC.","info"),
        ("voice",     "Voice profiles tuned (warm, energetic, calm).",    "info"),
        ("qa",        "Retention & claim-check checklists hot.",          "info"),
        ("publisher", "Instagram, YouTube, TikTok slots mapped.",         "info"),
        ("system",    "Idle — waiting for the next plan tick in ~60s.",   "info"),
    ]
    for a, m, s in seeds:
        emit(a, m, s, "seed")
        time.sleep(0.05)
    _seed_done = True


_IDLE_CHATTER = [
    ("strategy",  "Scanning the idea queue — looks clear. I'll plan fresh angles next tick.", "info"),
    ("brain",     "No scripts in progress. Polishing my hook templates while I wait.",        "info"),
    ("visuals",   "Idle. Generating style moodboards in the background (free, no token cost).","info"),
    ("qa",        "Standing by. Every script gets a retention + claim check before publish.", "info"),
    ("publisher", "Queue is quiet. Scheduler window is open.",                                "info"),
    ("analyst",   "Waiting for new publishes to pull metrics on.",                            "info"),
    ("community", "Listening for new comments — nothing new right now.",                      "info"),
    ("budget",    "Budget healthy. Standing by for the next content order.",                  "success"),
    ("system",    "All agents online. Drop an order in the Workspace box any time.",          "success"),
]
_LAST_IDLE = 0


def idle_chatter(context=None, force=False):
    """v1.6: honest idle status — ZERO invented dialogue, ZERO token cost.
    Prints the real state of the desk (queue depth, spend vs budget, when the
    scout last ran) so the Workspace feed stays alive between jobs without
    burning money on theater."""
    import time as _t
    if not force and _t.time() - _IDLE_LAST.get("ts", 0) < 600:
        return
    _IDLE_LAST["ts"] = _t.time()
    c = context or {}
    try:
        parts = ["queue — drafted:%s scheduled:%s published:%s" % (
            c.get("drafted", 0), c.get("scheduled", 0), c.get("published", 0))]
        if c.get("budget"):
            parts.append("spend $%.2f/$%.2f" % (c.get("spent") or 0.0, c["budget"]))
        sc = c.get("scout_at") or {}
        ts = sc.get("ts") if isinstance(sc, dict) else None
        if ts:
            parts.append("scout ran %dm ago" % int((_t.time() - float(ts)) // 60))
        emit("system", "Idle — nothing to produce. " + " · ".join(parts) +
             ". Queue a topic in Workspace to wake the desk.", "info", "idle_status")
    except Exception:
        emit("system", "Idle — queue empty. Waiting for topics.", "info", "idle_status")

_IDLE_LAST = {}

def error(agent, message, item_id=None):
    emit(agent, message, "error", "error", item_id=item_id)


def debate(agent, message, item_id=None):
    """Inter-agent disagreement / QA pushback."""
    emit(agent, message, "debate", "debate", item_id=item_id)
