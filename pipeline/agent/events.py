"""events.py — agent chatter feed.
Every agent writes a visible row into agent_events so the workspace feed
on the website shows agents talking/working in real time.

- emit(agent, message, status='info', action='note', item_id=None, cost_usd=0)
- heartbeat()   : called once on worker boot ("Strategy is online.")
- idle_chatter(): called every tick with an empty queue to look alive.
- Also inserts a small amount of seed chatter on first boot so the feed
  is never empty.
"""
import os, time, random
from . import config

# Agent registry — mirrors UI (RightPanel, workspace, project console).
# 18 agents total covering: research, brand, content, editing, QA, grading,
# publishing, marketing, analytics, community, finance.
AGENTS = {
    "system":      {"emoji": "⚙️", "role": "System"},
    "scout":       {"emoji": "🔭", "role": "Trend Scout"},
    "research":    {"emoji": "🔎", "role": "Researcher"},
    "architect":   {"emoji": "🏛️", "role": "Architect"},
    "strategist":  {"emoji": "📋", "role": "Strategist"},
    "planner":     {"emoji": "📅", "role": "Planner"},
    "strategy":    {"emoji": "🧠", "role": "Planner"},  # alias
    "brain":       {"emoji": "✍️", "role": "Script Writer"},
    "visuals":     {"emoji": "🎨", "role": "Visuals"},
    "voice":       {"emoji": "🎙️", "role": "Voice"},
    "composer":    {"emoji": "🎬", "role": "Editor"},
    "qa":          {"emoji": "🔍", "role": "QA"},
    "grader":      {"emoji": "🎯", "role": "Grader"},
    "seo":         {"emoji": "🔖", "role": "SEO"},
    "publisher":   {"emoji": "📤", "role": "Publisher"},
    "analyst":     {"emoji": "📊", "role": "Analytics"},
    "community":   {"emoji": "💬", "role": "Community"},
    "digest":      {"emoji": "📬", "role": "Digest"},
    "budget":      {"emoji": "💰", "role": "Budget"},
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


def idle_chatter(force=False):
    """One random idle line every ~2 minutes so the feed never goes stale."""
    global _LAST_IDLE
    now = time.time()
    if not force and (now - _LAST_IDLE) < 120:
        return
    _LAST_IDLE = now
    a, m, s = random.choice(_IDLE_CHATTER)
    emit(a, m, s, "idle")


def error(agent, message, item_id=None):
    emit(agent, message, "error", "error", item_id=item_id)


def debate(agent, message, item_id=None):
    """Inter-agent disagreement / QA pushback."""
    emit(agent, message, "debate", "debate", item_id=item_id)
