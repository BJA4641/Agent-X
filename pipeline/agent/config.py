"""config.py — env, capability flags, kill switch, budget cap."""
import os, json

def _load_env():
    for path in (".env", os.path.join(os.path.dirname(__file__), "..", ".env")):
        if os.path.exists(path):
            for line in open(path):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            return
_load_env()

def get(name, default=None):
    return os.environ.get(name, default)

def supabase_service_key():
    """Support both SUPABASE_SERVICE_KEY (pipeline) and SUPABASE_SERVICE_ROLE_KEY
    (Vercel/Supabase-dashboard convention). The pipeline prefers SERVICE_KEY but
    falls back to SERVICE_ROLE_KEY so you don't have to duplicate the variable."""
    return get("SUPABASE_SERVICE_KEY") or get("SUPABASE_SERVICE_ROLE_KEY")

# capability flags (drive dry-run vs live everywhere)
HAS_GEMINI    = bool(get("GEMINI_API_KEY") or get("GOOGLE_API_KEY"))
HAS_ANTHROPIC = bool(get("ANTHROPIC_API_KEY"))
HAS_ELEVEN    = bool(get("ELEVENLABS_API_KEY"))
HAS_SUPABASE  = bool(get("SUPABASE_URL") and supabase_service_key())
HAS_IG        = bool(get("IG_USER_ID") and get("IG_ACCESS_TOKEN"))
HAS_YT        = bool(get("YT_TOKEN_JSON")) and os.path.exists(get("YT_TOKEN_JSON", ""))

TENANT_ID  = get("TENANT_ID", "me")
BATCH_SIZE = int(get("BATCH_SIZE", "3"))
DAILY_BUDGET_USD = float(get("DAILY_BUDGET_USD", "3.0"))
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")

def _supabase():
    from supabase import create_client
    return create_client(get("SUPABASE_URL"), supabase_service_key())

def kill_switch_on() -> bool:
    """KILL_SWITCH=1 in env, a STOP file next to the pipeline, or the remote
    settings row (flipped from the web Studio page)."""
    if get("KILL_SWITCH", "0") == "1":
        return True
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.exists(os.path.join(here, "STOP")) or os.path.exists(os.path.join(here, "..", "STOP")):
        return True
    if HAS_SUPABASE:
        try:
            from supabase import create_client
            sb = create_client(get("SUPABASE_URL"), supabase_service_key())
            res = sb.table("settings").select("value").eq("tenant_id", TENANT_ID).eq("key", "kill_switch").execute()
            if res.data and res.data[0]["value"].get("on"):
                return True
        except Exception:
            pass
    return False

def load_prompt(name: str) -> tuple[str, str]:
    """Returns (prompt_text, version) from prompts/<name>.md; version = filename stem."""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        return f.read(), name

def capability_report() -> str:
    rows = [
        ("Visuals (Gemini image)", HAS_GEMINI),
        ("Scripts+Strategy (Claude)", HAS_ANTHROPIC),
        ("Premium voice (ElevenLabs)", HAS_ELEVEN),
        ("Board+Ledger (Supabase)", HAS_SUPABASE),
        ("Publish Instagram", HAS_IG),
        ("Publish YouTube", HAS_YT),
    ]
    lines = [f"  {'LIVE   ' if v else 'dry-run'}  {n}" for n, v in rows]
    lines.append(f"  kill switch: {'ON — nothing will run' if kill_switch_on() else 'off'}")
    lines.append(f"  daily budget: ${DAILY_BUDGET_USD:.2f}")
    return "\n".join(lines)


_SETTINGS_LOCAL = os.path.join(os.path.dirname(__file__), "..", "data", "settings-local.json")

def set_setting(key, value):
    if HAS_SUPABASE:
        try:
            _supabase().table("settings").upsert({"tenant_id": TENANT_ID, "key": key, "value": value}).execute()
            return
        except Exception:
            pass
    d = {}
    if os.path.exists(_SETTINGS_LOCAL):
        d = json.load(open(_SETTINGS_LOCAL))
    d[key] = value
    os.makedirs(os.path.dirname(_SETTINGS_LOCAL), exist_ok=True)
    json.dump(d, open(_SETTINGS_LOCAL, "w"))

def get_setting(key, default=None):
    if HAS_SUPABASE:
        try:
            res = _supabase().table("settings").select("value").eq("tenant_id", TENANT_ID).eq("key", key).execute()
            if res.data:
                return res.data[0]["value"]
        except Exception:
            pass
    if os.path.exists(_SETTINGS_LOCAL):
        return json.load(open(_SETTINGS_LOCAL)).get(key, default)
    return default
