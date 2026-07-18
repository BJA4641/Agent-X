"""community.py — the marketing agent talks back. Fetches comments on published
posts (IG Graph live, demo comments in stub) and drafts on-brand replies.
Replies are DRAFTS for Studio review by default; set COMMUNITY_AUTOREPLY=1 to post them
automatically once IG keys exist."""
import json
import urllib.request, urllib.parse
from . import config, ledger

EST_COST = 0.006
_DEMO_COMMENTS = [
    {"id": "demo1", "text": "Wait does this actually work offline??"},
    {"id": "demo2", "text": "🔥🔥🔥"},
    {"id": "demo3", "text": "AI slop, unfollowing"},
]

def _ig_media_id(item):
    for r in (item.get("payload", {}).get("publish_receipts") or []):
        if r.get("platform") == "instagram":
            return r.get("post_id")
    return None

def fetch_comments(item, stub=False) -> list:
    if stub or not config.HAS_IG:
        return list(_DEMO_COMMENTS) if stub else []
    media_id = _ig_media_id(item)
    if not media_id:
        return []
    try:
        url = (f"https://graph.facebook.com/v21.0/{media_id}/comments?fields=id,text"
               f"&access_token={config.get('IG_ACCESS_TOKEN')}")
        with urllib.request.urlopen(url, timeout=20) as r:
            data = json.loads(r.read().decode())
        return [{"id": c["id"], "text": c.get("text", "")} for c in data.get("data", [])]
    except Exception as e:
        ledger.record("community", ok=False, detail=f"fetch: {e}", item_id=item["id"])
        return []

def draft_replies(topic, comments, item_id=None) -> list:
    if not comments:
        return []
    if config.HAS_ANTHROPIC and ledger.budget_ok(EST_COST):
        try:
            import anthropic
            prompt, version = config.load_prompt("reply_v1")
            prompt = prompt.replace("{topic}", topic).replace("{comments}", json.dumps(comments))
            msg = anthropic.Anthropic().messages.create(
                model=config.get("CLAUDE_MODEL", "claude-sonnet-4-5"), max_tokens=500,
                messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in msg.content if b.type == "text")
            replies = json.loads(text[text.find("{"): text.rfind("}") + 1])["replies"]
            cost = (msg.usage.input_tokens * 3 + msg.usage.output_tokens * 15) / 1e6
            ledger.record("community", model=msg.model, prompt_version=version, cost_usd=cost, item_id=item_id)
            return replies
        except Exception as e:
            ledger.record("community", ok=False, detail=str(e), item_id=item_id)
    ledger.record("community", model="template", cost_usd=0, item_id=item_id)
    return [{"comment_id": c["id"],
             "text": "Great question — yes, and the pinned clip shows exactly how." if "?" in c["text"]
             else "Appreciate you 🙏"} for c in comments]

def post_reply(comment_id, text):
    url = f"https://graph.facebook.com/v21.0/{comment_id}/replies"
    data = urllib.parse.urlencode({"message": text, "access_token": config.get("IG_ACCESS_TOKEN")}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.loads(r.read().decode())

def run(item, stub=False) -> dict:
    """One community pass on one published item. Returns the payload patch."""
    existing = {c["comment_id"] for c in (item["payload"].get("community") or [])}
    comments = [c for c in fetch_comments(item, stub=stub) if c["id"] not in existing]
    if not comments:
        return {}
    drafts = draft_replies(item["topic"], comments, item_id=item["id"])
    by_id = {c["id"]: c["text"] for c in comments}
    rows, autoreply = [], config.get("COMMUNITY_AUTOREPLY", "0") == "1" and config.HAS_IG and not stub
    for d in drafts:
        row = {"comment_id": d["comment_id"], "comment": by_id.get(d["comment_id"], ""),
               "reply": d["text"], "replied": False}
        if autoreply:
            try:
                post_reply(d["comment_id"], d["text"]); row["replied"] = True
            except Exception as e:
                ledger.record("community", ok=False, detail=f"reply: {e}", item_id=item["id"])
        rows.append(row)
    return {"community": (item["payload"].get("community") or []) + rows}
