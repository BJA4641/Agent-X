"""publishing.py — Instagram Graph API + YouTube Data API. IDEMPOTENT.

Every (item, platform) gets a deterministic idempotency key; if a receipt with
that key already exists on the item, we refuse to post again (double-posting is
a ban vector). Dry-run by default; live when creds exist.

Instagram requires a PUBLIC https video URL -> upload_media() pushes the file
to Supabase Storage (bucket 'media', public) first.
"""
import hashlib, json, os, time, urllib.request, urllib.parse
from . import config, ledger

def idem_key(item_id: str, platform: str) -> str:
    return hashlib.sha256(f"{item_id}:{platform}".encode()).hexdigest()[:16]

def already_published(item: dict, platform: str) -> bool:
    key = idem_key(item["id"], platform)
    return any(r.get("idempotency_key") == key
               for r in (item.get("payload", {}).get("publish_receipts") or []))

def publish(item: dict, caption: str) -> list:
    receipts = list(item.get("payload", {}).get("publish_receipts") or [])
    for platform, enabled, fn in (("instagram", config.HAS_IG, _post_instagram),
                                  ("youtube", config.HAS_YT, _post_youtube)):
        if already_published(item, platform):
            continue
        key = idem_key(item["id"], platform)
        if not enabled:
            receipts.append({"platform": platform, "post_id": f"dryrun_{key}",
                             "idempotency_key": key, "dry_run": True})
            ledger.record(f"publish_{platform[:2]}", model="dry-run", item_id=item["id"])
            continue
        try:
            post_id = fn(item["payload"]["video_path"], caption)
            receipts.append({"platform": platform, "post_id": post_id,
                             "idempotency_key": key, "dry_run": False})
            ledger.record(f"publish_{platform[:2]}", item_id=item["id"], detail=post_id)
        except Exception as e:
            ledger.record(f"publish_{platform[:2]}", ok=False, detail=str(e), item_id=item["id"])
            raise
    return receipts

# ---------- Instagram ----------
def _post_instagram(video_path: str, caption: str) -> str:
    public_url = upload_media(video_path)
    user, token = config.get("IG_USER_ID"), config.get("IG_ACCESS_TOKEN")
    base = f"https://graph.facebook.com/v21.0/{user}"
    container = _post(f"{base}/media", {"media_type": "REELS", "video_url": public_url,
                                        "caption": caption, "access_token": token})["id"]
    for _ in range(40):  # wait for processing
        st = _get(f"https://graph.facebook.com/v21.0/{container}",
                  {"fields": "status_code", "access_token": token})
        if st.get("status_code") == "FINISHED":
            break
        time.sleep(5)
    return _post(f"{base}/media_publish", {"creation_id": container, "access_token": token})["id"]

# ---------- YouTube ----------
def _post_youtube(video_path: str, caption: str) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(config.get("YT_TOKEN_JSON", "yt_token.json"))
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": caption[:95], "description": caption, "categoryId": "27"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    res = None
    while res is None:
        _, res = req.next_chunk()
    return res["id"]

# ---------- storage ----------
def upload_media(video_path: str) -> str:
    """Supabase Storage 'media' bucket (public). Needed for IG. Returns public URL."""
    if not config.HAS_SUPABASE:
        raise RuntimeError("Instagram needs a public video URL: configure Supabase Storage first")
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
    name = f"{config.TENANT_ID}/{int(time.time())}_{os.path.basename(video_path)}"
    with open(video_path, "rb") as f:
        sb.storage.from_("media").upload(name, f.read(), {"content-type": "video/mp4"})
    return sb.storage.from_("media").get_public_url(name)

def _post(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def _get(url, params):
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=60) as r:
        return json.load(r)
