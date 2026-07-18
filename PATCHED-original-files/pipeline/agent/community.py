"""community.py — UPGRADE v0.3: brand-grounded replies, multi-tenant creds,
basic troll/escalation detection."""
import json, urllib.request, urllib.parse
from . import config, ledger, llm, brand

EST_COST = 0.006
_DEMO_COMMENTS = [
    {"id": "demo1", "text": "Wait does this actually work offline??"},
    {"id": "demo2", "text": "🔥🔥🔥"},
    {"id": "demo3", "text": "AI slop, unfollowing"},
]

def _creds(platform, uid):
    try:
        from . import connections
        return connections.credentials_for(uid, platform)
    except Exception:
        if platform == "instagram" and config.HAS_IG:
            return {"access_token": config.get("IG_ACCESS_TOKEN"), "user_id": config.get("IG_USER_ID")}
        return None

def _ig_media_id(item):
    for r in (item.get("payload", {}).get("publish_receipts") or []):
        if r.get("platform") == "instagram":
            return r.get("post_id")
    return None

def fetch_comments(item, stub=False, user_id=None) -> list:
    uid = user_id or item.get("tenant_id") or config.TENANT_ID
    if stub:
        return list(_DEMO_COMMENTS)
    media_id = _ig_media_id(item)
    creds = _creds("instagram", uid)
    if not media_id or not creds:
        return []
    try:
        url = (f"https://graph.facebook.com/v21.0/{media_id}/comments?fields=id,text"
               f"&access_token={creds['access_token']}")
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read().decode())
        return [{"id": c["id"], "text": c.get("text", "")} for c in data.get("data", [])]
    except Exception as e:
        ledger.record("community", ok=False, detail=f"fetch: {e}", item_id=item["id"])
        return []

def draft_replies(topic, comments, item_id=None, user_id=None) -> list:
    if not comments:
        return []
    grounding = brand.grounding_block(user_id)
    # Simple troll / crisis detection — escalate immediately
    CRISIS_KEYWORDS = {"lawsuit", "scam", "fraud", "dangerous", "harmful", "boycott", "unsubscribe", "never again"}
    escalations = []
    safe_comments = []
    for c in comments:
        low = c["text"].lower()
        if any(k in low for k in CRISIS_KEYWORDS) or c["text"].isupper() and len(c["text"]) > 30:
            escalations.append(c)
        else:
            safe_comments.append(c)
    if escalations:
        ledger.record("community", ok=False,
                      detail=f"escalated {len(escalations)} high-risk comments for human review", item_id=item["id"])
    if llm.ready() and ledger.budget_ok(EST_COST) and safe_comments:
        try:
            prompt, version = config.load_prompt("reply_v1")
            prompt = (
                f"{grounding}\n\n"
                "You reply in the EXACT brand voice above. Short, natural, no corporate fluff. "
                "For each comment: acknowledge; answer if a question; use one emoji max unless "
                "brand says no emojis; never over-promise; never argue; for negative-but-polite "
                "comments thank them and invite DM; for fire/1-word hype reply with matching energy.\n\n"
                f"Topic: {topic}\nComments: {json.dumps(safe_comments)}"
            )
            text, _cost, _model = llm.chat(prompt, max_tokens=500)
            try:
                replies = json.loads(text[text.find("{"): text.rfind("}") + 1])["replies"]
            except Exception:
                replies = [{"comment_id": c["id"], "text": "Appreciate you 🙏"} for c in safe_comments]
            ledger.record("community", model=_model, prompt_version=version, cost_usd=_cost, item_id=item["id"])
            # Mark escalations as draft-replies requiring human review
            for c in escalations:
                replies.append({"comment_id": c["id"], "text": "[ESCALATED — needs human review]", "needs_human": True})
            return replies
        except Exception as e:
            ledger.record("community", ok=False, detail=str(e), item_id=item["id"])
    ledger.record("community", model="template", cost_usd=0, item_id=item_id)
    return [{"comment_id": c["id"], "text": "Great question — yes, and the pinned clip shows exactly how." if "?" in c["text"] else "Appreciate you 🙏"} for c in safe_comments] + \
           [{"comment_id": c["id"], "text": "[ESCALATED — needs human review]", "needs_human": True} for c in escalations]

def post_reply(comment_id, text, creds):
    if text.startswith("[ESCALATED"): return None
    url = f"https://graph.facebook.com/v21.0/{comment_id}/replies"
    data = urllib.parse.urlencode({"message": text, "access_token": creds["access_token"]}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.loads(r.read().decode())

def run(item, stub=False, user_id=None):
    uid = user_id or item.get("tenant_id") or config.TENANT_ID
    existing = {c["comment_id"] for c in (item["payload"].get("community") or [])}
    comments = [c for c in fetch_comments(item, stub=stub, user_id=uid) if c["id"] not in existing]
    if not comments:
        return {}
    drafts = draft_replies(item["topic"], comments, item_id=item["id"], user_id=uid)
    by_id = {c["id"]: c["text"] for c in comments}
    rows, autoreply = [], config.get("COMMUNITY_AUTOREPLY", "0") == "1" and _creds("instagram", uid) and not stub
    for d in drafts:
        row = {"comment_id": d["comment_id"], "comment": by_id.get(d["comment_id"], ""),
               "reply": d["text"], "replied": False, "needs_human": bool(d.get("needs_human"))}
        if autoreply and not row["needs_human"]:
            try:
                post_reply(d["comment_id"], d["text"], _creds("instagram", uid)); row["replied"] = True
            except Exception as e:
                ledger.record("community", ok=False, detail=f"reply: {e}", item_id=item["id"])
        rows.append(row)
    return {"community": (item["payload"].get("community") or []) + rows}
