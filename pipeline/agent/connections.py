"""connections.py — per-user credential loader for the pipeline.

In a single-tenant (v0.2) world we read IG_ACCESS_TOKEN / YT_TOKEN_JSON from env.
In multi-tenant SaaS, a user_id is passed in and we read from user_connections
table, decrypt server-side, and return credentials. The pipeline never reads
from the browser, never exposes raw tokens, and always goes through this
module so adding a new platform is a one-file change.

Usage:
  from agent.connections import credentials_for
  creds = credentials_for(user_id, "instagram")
  # creds = {"access_token": "...", "user_id": "...", "display_name": "..."}
"""
from __future__ import annotations
import os, json
from typing import Optional
from . import config


def _env_creds() -> dict:
    """Single-tenant fallback (factory env vars)."""
    out = {}
    if config.get("IG_ACCESS_TOKEN") and config.get("IG_USER_ID"):
        out["instagram"] = {
            "access_token": config.get("IG_ACCESS_TOKEN"),
            "user_id": config.get("IG_USER_ID"),
            "display_name": config.get("IG_HANDLE") or None,
        }
    yt_path = config.get("YT_TOKEN_JSON")
    if yt_path and os.path.exists(yt_path):
        out["youtube"] = {"token_json_path": yt_path}
    if config.get("TIKTOK_ACCESS_TOKEN"):
        out["tiktok"] = {"access_token": config.get("TIKTOK_ACCESS_TOKEN"),
                         "open_id": config.get("TIKTOK_OPEN_ID")}
    if config.get("X_ACCESS_TOKEN"):
        out["x"] = {
            "access_token": config.get("X_ACCESS_TOKEN"),
            "access_secret": config.get("X_ACCESS_SECRET"),
            "api_key": config.get("X_API_KEY"),
            "api_secret": config.get("X_API_SECRET"),
        }
    if config.get("LINKEDIN_ACCESS_TOKEN"):
        out["linkedin"] = {"access_token": config.get("LINKEDIN_ACCESS_TOKEN"),
                           "organization_id": config.get("LINKEDIN_ORG_ID")}
    return out


def _decrypt_creds(ciphertext: str) -> dict:
    """
    Decrypt the ciphertext produced by the Postgres encrypt_creds RPC.
    Two strategies, in order:
      1. If a DECRYPT_CREDS_PASSPHRASE env var is set, use Fernet
         (symmetric encryption) directly in the worker. This matches the
         web-side encryption if you go that route in your RPC.
      2. Otherwise call a decrypt_creds Postgres RPC (preferred — key stays
         server-side, never leaves Postgres).
    For v1 you can skip encryption and use `credentials` jsonb directly —
    change the SELECT below to return credentials instead of cred_enc.
    """
    # --- Option A: Postgres RPC (preferred for production) ---
    if config.HAS_SUPABASE:
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
            res = sb.rpc("decrypt_creds", {"ciphertext": ciphertext}).execute()
            return res.data or {}
        except Exception:
            pass
    # --- Option B: local Fernet (set CONN_ENC_KEY in worker env) ---
    key = config.get("CONN_ENC_KEY")
    if key:
        try:
            from cryptography.fernet import Fernet
            return json.loads(Fernet(key).decrypt(ciphertext.encode()).decode())
        except Exception:
            pass
    return {}


def credentials_for(user_id: str, platform: str) -> Optional[dict]:
    """Return credentials for (user_id, platform) or None."""
    # 1. SaaS: look up per-user row
    if config.HAS_SUPABASE and user_id and user_id != "me":
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
            row = (sb.table("user_connections")
                     .select("credentials, cred_enc, display_name, status")
                     .eq("user_id", user_id).eq("platform", platform)
                     .limit(1).execute().data)
            if row and row[0]["status"] == "active":
                creds = row[0].get("credentials") or {}
                if row[0].get("cred_enc"):
                    creds = _decrypt_creds(row[0]["cred_enc"]) or creds
                creds = dict(creds)
                creds["display_name"] = row[0].get("display_name")
                return creds
        except Exception:
            pass
    # 2. Single-tenant fallback
    return _env_creds().get(platform)


def active_platforms_for_user(user_id: str) -> list[str]:
    """Return list of platform strings that have live credentials."""
    if config.HAS_SUPABASE and user_id and user_id != "me":
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.get("SUPABASE_SERVICE_KEY"))
            rows = (sb.table("user_connections")
                      .select("platform").eq("user_id", user_id).eq("status", "active")
                      .execute().data)
            return [r["platform"] for r in rows]
        except Exception:
            pass
    return list(_env_creds().keys())
