"""board.py — the source of truth. State machine with ENFORCED contracts.

  idea -> drafted -> approved -> scheduled -> published -> reported
                  -> rejected                          -> failed

An item cannot advance unless its payload carries the keys the next state
requires. Backend: Supabase if configured, else local JSON (zero setup).
"""
import json, os, time, uuid
from . import config

STATES = ["idea", "drafted", "approved", "rejected", "scheduled", "published", "reported", "failed"]

# payload keys REQUIRED to enter each state (the handoff contract)
CONTRACTS = {
    "drafted":   ["script", "video_path"],          # script = {hook, beats[], cta}
    "scheduled": ["script", "video_path"],
    "published": ["publish_receipts"],              # [{platform, post_id, idempotency_key}]
    "reported":  ["publish_receipts", "metrics"],
}

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA, exist_ok=True)
PATH = os.path.join(DATA, "board.json")

class ContractError(Exception):
    pass

def _check_contract(status, payload):
    missing = [k for k in CONTRACTS.get(status, []) if k not in (payload or {})]
    if missing:
        raise ContractError(f"cannot enter '{status}': payload missing {missing}")

# ---------- local backend ----------
def _load():
    if os.path.exists(PATH):
        return json.load(open(PATH))
    return []

def _save(items):
    json.dump(items, open(PATH, "w"), indent=1)

# ---------- public api ----------
def add(topic, status="idea", payload=None, scheduled_at=None):
    payload = payload or {}
    _check_contract(status, payload)
    item = {"id": str(uuid.uuid4()), "tenant_id": config.TENANT_ID, "status": status,
            "topic": topic, "payload": payload, "scheduled_at": scheduled_at,
            "created_at": int(time.time()), "updated_at": int(time.time())}
    if config.HAS_SUPABASE:
        row = dict(item); row.pop("created_at"); row.pop("updated_at")
        if scheduled_at: row["scheduled_at"] = _iso(scheduled_at)
        res = _sb().table("board_items").insert(row).execute()
        item["id"] = res.data[0]["id"]
        return item
    items = _load(); items.append(item); _save(items)
    return item

def update(item_id, status=None, payload_patch=None, scheduled_at=None):
    def apply(item):
        if payload_patch:
            item["payload"] = {**(item.get("payload") or {}), **payload_patch}
        if status:
            _check_contract(status, item["payload"])
            item["status"] = status
        if scheduled_at is not None:
            item["scheduled_at"] = scheduled_at
        item["updated_at"] = int(time.time())
        return item
    if config.HAS_SUPABASE:
        cur = _sb().table("board_items").select("*").eq("id", item_id).execute().data[0]
        cur = apply(cur)
        patch = {"status": cur["status"], "payload": cur["payload"], "updated_at": __import__("datetime").datetime.utcnow().isoformat()}
        if scheduled_at is not None: patch["scheduled_at"] = _iso(scheduled_at)
        _sb().table("board_items").update(patch).eq("id", item_id).execute()
        return cur
    items = _load()
    for it in items:
        if it["id"] == item_id:
            apply(it); _save(items); return it
    raise KeyError(item_id)

def list(status=None):
    if config.HAS_SUPABASE:
        q = _sb().table("board_items").select("*").eq("tenant_id", config.TENANT_ID)
        if status: q = q.eq("status", status)
        return q.order("created_at").execute().data
    items = [i for i in _load() if i["tenant_id"] == config.TENANT_ID]
    return [i for i in items if i["status"] == status] if status else items

def get(item_id):
    for it in list():
        if it["id"] == item_id: return it
    raise KeyError(item_id)

def _iso(ts):
    import datetime
    return datetime.datetime.utcfromtimestamp(int(ts)).isoformat() if isinstance(ts, (int, float)) else ts

def _sb():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
