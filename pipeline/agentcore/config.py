"""agentcore/config.py — thin wrapper over agent.config so agentcore doesn't
hard-depend on the agent package for env/bootstrap.
"""
from __future__ import annotations
import os


def _ensure_env():
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "..", ".env"), os.path.join(here, "..", "..", ".env")):
        if os.path.exists(path):
            for line in open(path):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return


_ensure_env()


def get(name, default=None):
    return os.environ.get(name, default)


def supabase_service_key():
    return get("SUPABASE_SERVICE_KEY") or get("SUPABASE_SERVICE_ROLE_KEY")


def has_supabase():
    return bool(get("SUPABASE_URL") and supabase_service_key())


TENANT_ID = get("TENANT_ID", "me")
DAILY_BUDGET_USD = float(get("DAILY_BUDGET_USD", "1.50"))


def supabase():
    """Lazy create supabase client. Returns None if not configured."""
    if not has_supabase():
        return None
    try:
        from supabase import create_client
        return create_client(get("SUPABASE_URL"), supabase_service_key())
    except Exception:
        return None


def econ_mode_on() -> bool:
    """v5.8 ECON MODE: prefer free visual providers (Gemini free tier /
    procedural) and skip the paid image branch. Settings key `econ_mode`."""
    if get("ECON_MODE", "0") == "1":
        return True
    sb = supabase()
    if sb:
        try:
            res = (sb.table("settings").select("value")
                   .eq("tenant_id", TENANT_ID).eq("key", "econ_mode").execute())
            if res.data and res.data[0]["value"].get("on"):
                return True
        except Exception:
            pass
    return False


def soft_pause_on() -> bool:
    """v5.7 SOFT PAUSE: take no NEW content work, but let in-flight jobs finish.
    Gentler than the kill switch (which blocks everything immediately)."""
    if get("SOFT_PAUSE", "0") == "1":
        return True
    sb = supabase()
    if sb:
        try:
            res = (sb.table("settings").select("value")
                   .eq("tenant_id", TENANT_ID).eq("key", "soft_pause").execute())
            if res.data and res.data[0]["value"].get("on"):
                return True
        except Exception:
            pass
    return False


def kill_switch_on() -> bool:
    if get("KILL_SWITCH", "0") == "1":
        return True
    # Check for STOP file in two likely locations
    for loc in (os.path.join(os.path.dirname(__file__), "..", "STOP"),
                os.path.join(os.path.dirname(__file__), "..", "..", "STOP")):
        if os.path.exists(loc):
            return True
    sb = supabase()
    if sb:
        try:
            res = (sb.table("settings").select("value")
                   .eq("tenant_id", TENANT_ID).eq("key", "kill_switch").execute())
            if res.data and res.data[0]["value"].get("on"):
                return True
        except Exception:
            pass
    return False
