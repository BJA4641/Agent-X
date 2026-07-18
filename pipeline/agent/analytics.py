"""analytics.py — pull metrics per published item. Live IG/YT when creds exist,
deterministic stub otherwise (so the loop and Strategy always have data)."""
import hashlib, json, urllib.request, urllib.parse
from . import config, ledger

def collect(item: dict) -> dict:
    metrics = {}
    for r in item["payload"].get("publish_receipts", []):
        p = r["platform"]
        if r.get("dry_run"):
            h = int(hashlib.sha256(r["post_id"].encode()).hexdigest(), 16)
            metrics[p] = {"views": 500 + h % 4500, "likes": 20 + h % 300, "comments": h % 40}
        elif p == "instagram" and config.HAS_IG:
            metrics[p] = _ig(r["post_id"])
        elif p == "youtube" and config.HAS_YT:
            metrics[p] = _yt(r["post_id"])
    ledger.record("analytics", item_id=item["id"], detail=json.dumps(metrics)[:200])
    return metrics

def _ig(post_id):
    token = config.get("IG_ACCESS_TOKEN")
    url = f"https://graph.facebook.com/v21.0/{post_id}/insights?" + urllib.parse.urlencode(
        {"metric": "views,likes,comments", "access_token": token})
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.load(r)
    out = {}
    for m in data.get("data", []):
        out[m["name"]] = (m.get("values") or [{}])[0].get("value", 0)
    return {"views": out.get("views", 0), "likes": out.get("likes", 0), "comments": out.get("comments", 0)}

def _yt(video_id):
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(config.get("YT_TOKEN_JSON", "yt_token.json"))
    yt = build("youtube", "v3", credentials=creds)
    res = yt.videos().list(part="statistics", id=video_id).execute()
    s = res["items"][0]["statistics"] if res.get("items") else {}
    return {"views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0))}
