"""analytics.py — UPGRADE v0.3: accepts optional user_id for multi-tenant cred lookup."""
import hashlib, json, urllib.request, urllib.parse
from . import config, ledger

def collect(item: dict, user_id=None) -> dict:
    metrics = {}
    uid = user_id or item.get("tenant_id") or config.TENANT_ID
    for r in item.get("payload", {}).get("publish_receipts", []):
        p = r["platform"]
        if r.get("dry_run"):
            h = int(hashlib.sha256(r["post_id"].encode()).hexdigest(), 16)
            metrics[p] = {"views": 500 + h % 4500, "likes": 20 + h % 300, "comments": h % 40}
        elif p == "instagram":
            creds = _creds(p, uid)
            if creds: metrics[p] = _ig(r["post_id"], creds)
        elif p == "youtube":
            creds = _creds(p, uid)
            if creds: metrics[p] = _yt(r["post_id"], creds)
    ledger.record("analytics", item_id=item["id"], detail=json.dumps(metrics)[:200])
    return metrics

def _creds(platform, uid):
    try:
        from . import connections
        return connections.credentials_for(uid, platform)
    except Exception:
        return None

def _ig(post_id, creds):
    token = creds.get("access_token")
    url = f"https://graph.facebook.com/v21.0/{post_id}/insights?" + urllib.parse.urlencode(
        {"metric": "views,likes,comments", "access_token": token})
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    out = {}
    for m in data.get("data", []):
        out[m["name"]] = (m.get("values") or [{}])[0].get("value", 0)
    return {"views": out.get("views", 0), "likes": out.get("likes", 0), "comments": out.get("comments", 0)}

def _yt(video_id, creds):
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    if creds.get("token_json_path"):
        c = Credentials.from_authorized_user_file(creds["token_json_path"])
    else:
        c = Credentials(token=creds.get("access_token"), refresh_token=creds.get("refresh_token"),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=creds.get("client_id"), client_secret=creds.get("client_secret"))
    yt = build("youtube", "v3", credentials=c)
    res = yt.videos().list(part="statistics", id=video_id).execute()
    s = res["items"][0]["statistics"] if res.get("items") else {}
    return {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0))}
