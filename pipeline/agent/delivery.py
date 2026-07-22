"""
agent/delivery.py — v5.8 render delivery (Batch 4)
Uploads finished renders (mp4 / carousel images) to Supabase Storage bucket
`renders` so Studio can play/download them and files survive redeploys.
Container disk on Railway is ephemeral: anything not uploaded is lost.

Layout in bucket:  {item_id}/reel.mp4   {item_id}/slide_1.jpg .. slide_5.jpg
All functions are best-effort: they return None/[] on failure and never raise,
so a storage hiccup degrades to the old behavior instead of failing the job.
"""
from __future__ import annotations
import os

BUCKET = "renders"


def _public_url(sb, path: str) -> str | None:
    try:
        res = sb.storage.from_(BUCKET).get_public_url(path)
        # supabase-py returns str (v2) or dict-ish; normalize
        if isinstance(res, str):
            return res.split("?")[0]
        return (res.get("publicUrl") or res.get("public_url") or "").split("?")[0] or None
    except Exception:
        return None


def _upload(sb, local_path: str, dest_path: str, content_type: str) -> str | None:
    if not sb or not local_path or not os.path.exists(local_path):
        return None
    try:
        with open(local_path, "rb") as f:
            data = f.read()
        try:
            sb.storage.from_(BUCKET).upload(
                dest_path, data, {"content-type": content_type, "upsert": "true"})
        except Exception as e:
            # upsert flag name varies across client versions; retry after remove
            if "exists" in str(e).lower() or "duplicate" in str(e).lower():
                try:
                    sb.storage.from_(BUCKET).remove([dest_path])
                    sb.storage.from_(BUCKET).upload(
                        dest_path, data, {"content-type": content_type})
                except Exception:
                    return None
            else:
                return None
        return _public_url(sb, dest_path)
    except Exception:
        return None


def upload_video(sb, local_path: str, item_id) -> str | None:
    """Upload a rendered reel; returns public URL or None."""
    return _upload(sb, local_path, f"{item_id}/reel.mp4", "video/mp4")


def upload_images(sb, local_paths: list, item_id) -> list:
    """Upload carousel slides in order; returns list of public URLs (skips failures)."""
    urls = []
    for i, p in enumerate(local_paths or [], start=1):
        u = _upload(sb, p, f"{item_id}/slide_{i}.jpg", "image/jpeg")
        if u:
            urls.append(u)
    return urls
