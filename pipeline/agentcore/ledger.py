"""agentcore/ledger.py — cost ledger shared by the new worker-based pipeline.

Writes into the same run_ledger table used by the legacy agent/ path so the
dashboard numbers stay consistent during the migration. Falls back to a
local JSONL file when Supabase is unavailable.
"""
from __future__ import annotations
import datetime, json, os, traceback
from . import config as _cfg

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)
LOCAL_PATH = os.path.join(DATA_DIR, "ledger.jsonl")


def _sb():
    return _cfg.supabase()


def record(step: str, *, model: str = "", prompt_version: str = "",
           cost_usd: float = 0.0, ok: bool = True, detail: str = "",
           item_id: str = None, job_id: str = None, account_id=None):
    """Append one ledger row. Never raises."""
    row = {
        "tenant_id": _cfg.TENANT_ID,
        "item_id": str(item_id) if item_id else None,
        "step": step, "model": model or "", "prompt_version": prompt_version or "",
        "cost_usd": round(float(cost_usd or 0), 5),
        "ok": bool(ok), "detail": (detail or "")[:400],
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    if job_id:
        row["job_id"] = job_id
    if account_id:
        row["account_id"] = str(account_id)
    sb = _sb()
    if sb:
        try:
            sb.table("run_ledger").insert(row).execute()
            return row
        except Exception:
            row["detail"] += " | supabase ledger failed"
    try:
        with open(LOCAL_PATH, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception:
        traceback.print_exc()
    return row


def spent_today() -> float:
    today = datetime.date.today().isoformat()
    sb = _sb()
    if sb:
        try:
            res = (sb.table("run_ledger").select("cost_usd")
                   .eq("tenant_id", _cfg.TENANT_ID)
                   .gte("created_at", today).execute())
            return sum(float(r.get("cost_usd") or 0) for r in (res.data or []))
        except Exception:
            pass
    total = 0.0
    if os.path.exists(LOCAL_PATH):
        for line in open(LOCAL_PATH):
            try:
                r = json.loads(line)
                if str(r.get("created_at", ""))[:10] == today:
                    total += float(r.get("cost_usd") or 0)
            except Exception:
                continue
    return total


def budget_ok(next_cost_usd: float, daily_budget: float = None) -> bool:
    cap = daily_budget if daily_budget is not None else _cfg.DAILY_BUDGET_USD
    return (spent_today() + next_cost_usd) <= cap
