"""projects.py v4.1 — helpers for working with projects / project_accounts."""
from . import config


def list_active_accounts():
    """Return accounts that are NOT paused AND whose parent project is NOT paused."""
    if not config.HAS_SUPABASE: return []
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        res = (sb.table("project_accounts")
               .select("id,name,handle,niche,project_id,platforms,status,daily_budget_usd,posts_per_day")
               .eq("paused", False)
               .execute())
        out = []
        for a in res.data or []:
            try:
                pj = sb.table("projects").select("paused,name").eq("id", a["project_id"]).single().execute().data
                if pj and not pj.get("paused"):
                    a["project_name"] = pj.get("name")
                    out.append(a)
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[projects] list_active_accounts failed: {e}")
        return []


def get_account(account_id: str):
    if not config.HAS_SUPABASE: return None
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        a = sb.table("project_accounts").select("*").eq("id", account_id).single().execute().data
        if not a: return None
        pj = sb.table("projects").select("paused,name").eq("id", a["project_id"]).single().execute().data
        a["projects"] = pj or {}
        return a
    except Exception:
        return None


def is_active(account_id: str) -> bool:
    a = get_account(account_id)
    if not a: return False
    if a.get("paused"): return False
    if (a.get("projects") or {}).get("paused"): return False
    return True
