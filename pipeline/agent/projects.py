"""projects.py — v1.6 multi-project support.
The web app stores projects (name + niche + platforms) per user; the pipeline
plans content PER ACTIVE PROJECT so one account can run several brands at once.
Zero-config fallback: with no Supabase or an empty table, you get exactly the
old single-project behavior (env NICHE / PROJECT_NAME)."""
import time
from . import config

_cache = {"at": 0.0, "rows": None}
MAX_PROJECTS = 4  # planning cost guard — budget still rules above this


def active_projects() -> list:
    """List of {'id','name','niche','platforms','status'} — always >= 1 entry."""
    if _cache["rows"] is not None and time.time() - _cache["at"] < 120:
        return _cache["rows"]
    rows = None
    if config.HAS_SUPABASE:
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
            rows = (sb.table("projects").select("id,name,niche,platforms,status")
                    .eq("status", "active").order("created_at")
                    .limit(MAX_PROJECTS).execute().data) or None
        except Exception:
            rows = None
    if not rows:
        rows = [{"id": None, "name": config.get("PROJECT_NAME", "default"),
                 "niche": config.get("NICHE") or None, "platforms": [], "status": "active"}]
    _cache.update(at=time.time(), rows=rows)
    return rows
