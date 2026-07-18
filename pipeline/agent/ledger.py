"""ledger.py — every paid/step call becomes a row. Local JSONL, or Supabase if configured.
This is cost truth today and SaaS metering tomorrow."""
import json, os, time, datetime
from . import config

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA, exist_ok=True)
PATH = os.path.join(DATA, "ledger.jsonl")

def record(step, model=None, prompt_version=None, cost_usd=0.0, ok=True, detail="", item_id=None):
    row = {"tenant_id": config.TENANT_ID, "item_id": item_id, "step": step, "model": model,
           "prompt_version": prompt_version, "cost_usd": round(float(cost_usd), 5),
           "ok": ok, "detail": detail[:400], "created_at": datetime.datetime.utcnow().isoformat()}
    if config.HAS_SUPABASE:
        try:
            _sb().table("run_ledger").insert(row).execute()
            return row
        except Exception as e:
            row["detail"] += f" | supabase ledger failed: {e}"
    with open(PATH, "a") as f:
        f.write(json.dumps(row) + "\n")
    return row

def spent_today() -> float:
    today = datetime.date.today().isoformat()
    if config.HAS_SUPABASE:
        try:
            res = _sb().table("run_ledger").select("cost_usd").gte("created_at", today).execute()
            return sum(float(r["cost_usd"]) for r in res.data)
        except Exception:
            pass
    total = 0.0
    if os.path.exists(PATH):
        for line in open(PATH):
            try:
                r = json.loads(line)
                if r["created_at"][:10] == today:
                    total += float(r["cost_usd"])
            except Exception:
                continue
    return total

def spent_since(days=7) -> float:
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    total = 0.0
    if config.HAS_SUPABASE:
        try:
            res = _sb().table("run_ledger").select("cost_usd").eq("tenant_id", config.TENANT_ID).gte("created_at", cutoff).execute()
            return sum(r["cost_usd"] or 0 for r in res.data)
        except Exception:
            pass
    if os.path.exists(PATH):
        for line in open(PATH):
            try:
                r = json.loads(line)
                if r.get("created_at", "") >= cutoff:
                    total += r.get("cost_usd") or 0
            except Exception:
                continue
    return total

_budget_cache = {"at": 0.0, "usd": None}

def daily_budget() -> float:
    """Budget set from the Studio settings page (DB), falling back to the env var."""
    import time
    if time.time() - _budget_cache["at"] > 60:
        val = None
        if config.HAS_SUPABASE:
            try:
                r = _sb().table("settings").select("value").eq("tenant_id", config.TENANT_ID).eq("key", "daily_budget").execute().data
                if r: val = float((r[0]["value"] or {}).get("usd"))
            except Exception:
                val = None
        _budget_cache.update(at=time.time(), usd=val if val is not None else config.DAILY_BUDGET_USD)
    return _budget_cache["usd"]

def budget_ok(next_cost: float) -> bool:
    return (spent_today() + next_cost) <= daily_budget()

def _sb():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
