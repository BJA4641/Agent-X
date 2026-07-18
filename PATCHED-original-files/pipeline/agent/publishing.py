"""publishing.py — Instagram Graph API + YouTube Data API. IDEMPOTENT.
UPGRADE v0.3: accept optional user_id to look up per-user credentials
via connections.py instead of global env vars.
"""
import hashlib, json, os, time, urllib.request, urllib.parse
from . import config, ledger

def idem_key(item_id: str, platform: str) -> str:
    return hashlib.sha256(f"{item_id}:{platform}".encode()).hexdigest()[:16]

def already_published(item: dict, platform: str) -> bool:
    key = idem_key(item["id"], platform)
    return any(r.get("idempotency_key") == key
               for r in (item.get("payload", {}).get("publish_receipts") or []))

def _creds_for(platform: str, user_id=None) -> dict:
    """Return credentials for (user_id, platform). Tries connections module
    first (multi-tenant), then falls back to env vars (single-tenant)."""
    try:
        from . import connections
        c = connections.credentials_for(user_id or config.TENANT_ID, platform)
        if c: return c
    except Exception:
        pass
    # Env fallback (single-tenant / factory)
    if platform == "instagram":
        if config.get("IG_ACCESS_TOKEN") and config.get("IG_USER_ID"):
            return {"access_token": config.get("IG_ACCESS_TOKEN"), "user_id": config.get("IG_USER_ID")}
    if platform == "youtube":
        yt = config.get("YT_TOKEN_JSON")
        if yt and os.path.exists(yt):
            return {"token_json_path": yt}
    return {}


def publish(item: dict, caption: str, user_id=None) -> list:
    receipts = list(item.get("payload", {}).get("publish_receipts") or [])
    uid = user_id or item.get("tenant_id") or config.TENANT_ID
    platforms_enabled = [
        ("instagram", bool(_creds_for("instagram", uid))),
        ("youtube",   bool(_creds_for("youtube", uid))),
    ]
    # Optional future platforms:
    for pf in ("tiktok", "x", "linkedin", "pinterest", "facebook"):
        if _creds_for(pf, uid):
            platforms_enabled.append((pf, True))
    for platform, enabled in platforms_enabled:
        if already_published(item, platform):
            continue
        key = idem_key(item["id"], platform)
        if not enabled:
            receipts.append({"platform": platform, "post_id": f"dryrun_{key}",
                             "idempotency_key": key, "dry_run": True})
            ledger.record(f"publish_{platform[:2]}", model="dry-run", item_id=item["id"])
            continue
        try:
            post_id = _dispatch(platform, item["payload"]["video_path"], caption, uid)
            receipts.append({"platform": platform, "post_id": post_id,
                             "idempotency_key": key, "dry_run": False})
            ledger.record(f"publish_{platform[:2]}", item_id=item["id"], detail=post_id)
        except Exception as e:
            ledger.record(f"publish_{platform[:2]}", ok=False, detail=str(e), item_id=item["id"])
            raise
    return receipts


def _dispatch(platform: str, video_path: str, caption: str, user_id: str) -> str:
    creds = _creds_for(platform, user_id)
    if platform == "instagram":
        return _post_instagram(video_path, caption, creds)
    if platform == "youtube":
        return _post_youtube(video_path, caption, creds)
    raise RuntimeError(f"Platform {platform} dispatch not yet implemented")

# ---------- Instagram ----------
def _post_instagram(video_path: str, caption: str, creds: dict) -> str:
    public_url = upload_media(video_path)
    user, token = creds.get("user_id"), creds.get("access_token")
    base = f"https://graph.facebook.com/v21.0/{user}"
    container = _post(f"{base}/media", {"media_type": "REELS", "video_url": public_url,
                                        "caption": caption, "access_token": token})["id"]
    for _ in range(40):
        st = _get(f"https://graph.facebook.com/v21.0/{container}",
                  {"fields": "status_code", "access_token": token})
        if st.get("status_code") == "FINISHED":
            break
        time.sleep(5)
    return _post(f"{base}/media_publish", {"creation_id": container, "access_token": token})["id"]

# ---------- YouTube ----------
def _post_youtube(video_path: str, caption: str, creds: dict) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.oauth2.credentials import Credentials
    # creds may contain {token_json_path} OR {access_token, refresh_token, client_id, client_secret}
    if creds.get("token_json_path"):
        creds_obj = Credentials.from_authorized_user_file(creds["token_json_path"])
    else:
        creds_obj = Credentials(
            token=creds.get("access_token"),
            refresh_token=creds.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=creds.get("client_id"),
            client_secret=creds.get("client_secret"),
        )
    yt = build("youtube", "v3", credentials=creds_obj)
    body = {"snippet": {"title": caption[:95], "description": caption, "categoryId": "27"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    res = None
    while res is None:
        _, res = req.next_chunk()
    return res["id"]

# ---------- storage ----------
def upload_media(video_path: str, user_id=None) -> str:
    """Supabase Storage 'media' bucket (public). Returns public URL."""
    if not config.HAS_SUPABASE:
        raise RuntimeError("Instagram needs a public video URL: configure Supabase Storage first")
    from supabase import create_client
    sb = create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
    name = f"{user_id or config.TENANT_ID}/{int(time.time())}_{os.path.basename(video_path)}"
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
