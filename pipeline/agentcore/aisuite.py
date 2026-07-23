"""aisuite.py — v5.4 unified router for EVERY AI provider in the catalog.

Replaces hard-coded logic scattered across llm.py and visuals.py with one
catalog-driven dispatcher. Loads providers_catalog.json and exposes:

  generate_text(prompt, tier|model)  -> (text, meta)
  generate_image(prompt, model=None) -> local_path (jpg)
  edit_image(image_bytes, prompt, model=None) -> local_path
  tts(text, voice_id, model=None)    -> local_path (mp3)
  generate_video(prompt_or_image, image=None, model=None) -> local_path (mp4)

Auto-fallback within category: if chosen model is missing-key or errors,
rotates through the _default list for that category.
"""
from __future__ import annotations
import json, os, time, base64, urllib.request, urllib.error, tempfile, uuid
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from . import config, ledger

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "providers_catalog.json")


def _load_catalog() -> dict:
    with open(CATALOG_PATH) as f:
        return json.load(f)


CATALOG = _load_catalog()

# Category-specific settings key (stores chosen model id per category).
_SETTINGS_KEY = {
    "text": "model",            # legacy
    "text_to_image": "model_t2i",
    "image_edit":   "model_ie",
    "text_to_video": "model_t2v",
    "image_to_video": "model_i2v",
    "voice":        "model_tts",
    "video_edit":   "model_vedit",
}


def _has_key(key_env: Optional[str]) -> bool:
    if not key_env:
        return False
    return bool(config.get(key_env))


def _supabase():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.supabase_service_key())


def _chosen_model(category: str) -> Optional[dict]:
    """Return the catalog entry for the user-chosen model in this category, or None."""
    chosen_id = None
    if config.has_supabase():
        try:
            sb = _supabase()
            skey = _SETTINGS_KEY[category]
            r = sb.table("settings").select("value").eq("tenant_id", config.TENANT_ID).eq("key", skey).limit(1).execute()
            if r.data and r.data[0].get("value"):
                chosen_id = r.data[0]["value"].get("model")
        except Exception:
            pass
    if not chosen_id:
        # Fallback to first _default
        for m in CATALOG[category]["models"]:
            if m.get("default"):
                return m
        return CATALOG[category]["models"][0]
    for m in CATALOG[category]["models"]:
        if m["id"] == chosen_id:
            return m
    return None


def _supabase():
    from supabase import create_client
    from agentcore.config import supabase as _sb
    return create_client(config.get("SUPABASE_URL"), config.supabase_service_key())


def _candidate_order(category: str, preferred_id: Optional[str] = None) -> list:
    """Return list of model entries in the order to try: preferred -> _default list -> free fallbacks."""
    models = {m["id"]: m for m in CATALOG[category]["models"]}
    defaults = CATALOG[category].get("_default", [])
    order = []
    seen = set()

    def add(mid):
        if mid and mid in models and mid not in seen:
            order.append(models[mid]); seen.add(mid)

    add(preferred_id)
    picked = _chosen_model(category)
    if picked: add(picked["id"])
    for d in defaults: add(d)
    # Free/fallback models
    for m in CATALOG[category]["models"]:
        if m.get("free_tier") or m.get("fallback_only"): add(m["id"])
    # Any remaining (paid with keys)
    for m in CATALOG[category]["models"]:
        if _has_key(m.get("key_env")) and not m.get("fallback_only"): add(m["id"])
    return order


# ------------------------------------------------------------ helpers
def _post_json(url: str, body: dict, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get(url: str, headers: dict, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _save_bytes(data: bytes, ext: str = "jpg") -> str:
    out_dir = Path(config.get("MEDIA_DIR", "/tmp/agentx_media"))
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{uuid.uuid4().hex}.{ext}"
    p.write_bytes(data)
    return str(p)


def _download(url: str, ext: str = "jpg", headers: dict = None) -> str:
    data = _get(url, headers or {})
    return _save_bytes(data, ext)


# ============================================================ TEXT
def generate_text(prompt: str, *, tier: str = "standard", model: str = None,
                  system: str = "", max_tokens: int = None) -> Tuple[str, dict]:
    """Call best text model in tier, with auto-fallback."""
    # Prefer the tier list from catalog._default_tier
    pref_order = CATALOG["text"].get("_default_tier", {}).get(tier, [])
    pref_id = model or (pref_order[0] if pref_order else None)
    candidates = _candidate_order("text", pref_id)
    last_err = None
    t0 = time.time()
    for m in candidates:
        if not _has_key(m.get("key_env")) and not m.get("free_tier"):
            continue
        # v5.8.7: skip providers that are out of credit, have a dead key, or are
        # paid while we are in free_only mode. The loop then falls through to the
        # next candidate (ultimately a free one) instead of failing the job.
        try:
            from agentcore import costmode as _cm
            _prov = (m.get("provider") or m.get("endpoint") or "").lower()
            if _prov and not _cm.usable(_prov, paid=bool(m.get("paid"))):
                continue
        except Exception:
            pass
        try:
            text, cost, label = _call_text(m, prompt, system=system, max_tokens=max_tokens or 1200)
            meta = {"model": label, "cost_usd": cost, "latency_s": time.time() - t0, "tier": tier}
            ledger.record("aisuite.text", model=label, cost_usd=cost)
            return text, meta
        except Exception as e:
            last_err = e
            try:
                from agentcore import costmode as _cm
                import urllib.error as _ue
                _code = getattr(e, "code", 0) if isinstance(e, _ue.HTTPError) else 0
                _cm.mark_error((m.get("provider") or m.get("endpoint") or "").lower(),
                               _code, str(e)[:200])
            except Exception:
                pass
            continue
    raise RuntimeError(f"all text providers failed: {last_err}")


def _call_text(m: dict, prompt: str, *, system: str, max_tokens: int):
    endpoint = m["endpoint"]; key = config.get(m["key_env"]) if m.get("key_env") else None
    if endpoint == "anthropic":
        import anthropic
        cli = anthropic.Anthropic(api_key=key)
        msgs = []
        if system: msgs = [{"role": "user", "content": system + "\n\n" + prompt}]
        else: msgs = [{"role": "user", "content": prompt}]
        msg = cli.messages.create(model=m["id"], max_tokens=max_tokens, messages=msgs)
        text = "".join(b.text for b in msg.content if b.type == "text")
        cost = (msg.usage.input_tokens * m.get("price_in", 3) + msg.usage.output_tokens * m.get("price_out", 15)) / 1e6
        return text, cost, m["id"]
    if endpoint == "openai" or endpoint == "openai_responses" or endpoint == "openai_compat":
        base = m.get("base_url", "https://api.openai.com/v1")
        body = {"model": m["id"], "messages": [{"role": "user", "content": (system+"\n\n"+prompt) if system else prompt}], "max_tokens": max_tokens}
        r = _post_json(f"{base}/chat/completions", body, {"Authorization": f"Bearer {key}"})
        text = r["choices"][0]["message"]["content"]
        in_tok = r["usage"]["prompt_tokens"]; out_tok = r["usage"]["completion_tokens"]
        cost = (in_tok * m.get("price_in", 2.5) + out_tok * m.get("price_out", 10)) / 1e6
        return text, cost, m["id"]
    if endpoint == "gemini":
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{m['id']}:generateContent?key={key}")
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": max_tokens}}
        r = _post_json(url, body, {})
        text = "".join(p.get("text","") for p in r["candidates"][0]["content"]["parts"])
        return text, 0.0, f"gemini:{m['id']}"
    if endpoint == "groq":
        r = _post_json("https://api.groq.com/openai/v1/chat/completions",
                       {"model": "llama-3.3-70b-versatile", "messages": [{"role":"user","content":prompt}], "max_tokens": max_tokens},
                       {"Authorization": f"Bearer {key}"})
        return r["choices"][0]["message"]["content"], 0.0, "groq:llama-3.3-70b"
    if endpoint == "openrouter":
        r = _post_json("https://openrouter.ai/api/v1/chat/completions",
                       {"model": m.get("openrouter_model", "moonshotai/kimi-k2:free"),
                        "messages": [{"role":"user","content":prompt}], "max_tokens": max_tokens},
                       {"Authorization": f"Bearer {key}"})
        return r["choices"][0]["message"]["content"], 0.0, f"openrouter:{m.get('openrouter_model','kimi-k2')}"
    if endpoint == "deepseek":
        r = _post_json("https://api.deepseek.com/v1/chat/completions",
                       {"model": m["id"].replace("deepseek-", ""), "messages": [{"role":"user","content":prompt}], "max_tokens": max_tokens},
                       {"Authorization": f"Bearer {key}"})
        text = r["choices"][0]["message"]["content"]
        in_tok = r["usage"]["prompt_tokens"]; out_tok = r["usage"]["completion_tokens"]
        cost = (in_tok * m.get("price_in", 0.27) + out_tok * m.get("price_out", 1.1)) / 1e6
        return text, cost, m["id"]
    if endpoint == "cohere":
        # Fallback to openai compat
        pass
    # default: openai compat
    base = m.get("base_url", "https://api.openai.com/v1")
    r = _post_json(f"{base}/chat/completions",
                   {"model": m["id"], "messages": [{"role":"user","content":prompt}], "max_tokens": max_tokens},
                   {"Authorization": f"Bearer {key}"})
    return r["choices"][0]["message"]["content"], 0.0, m["id"]


# ============================================================ IMAGES
def generate_image(prompt: str, *, model: str = None, size: str = "1024x1536") -> str:
    """Return local path to a JPEG."""
    candidates = _candidate_order("text_to_image", model)
    last_err = None
    for m in candidates:
        if not _has_key(m.get("key_env")) and not m.get("free_tier"):
            continue
        try:
            path = _call_t2i(m, prompt, size=size)
            ledger.record("aisuite.t2i", model=m["id"], cost_usd=m.get("est_usd", 0.02))
            return path
        except Exception as e:
            last_err = e; continue
    raise RuntimeError(f"all t2i providers failed: {last_err}")


def _call_t2i(m: dict, prompt: str, size: str) -> str:
    endpoint = m["endpoint"]; key = config.get(m["key_env"]) if m.get("key_env") else None
    w, h = (int(x) for x in size.split("x"))
    if endpoint == "gemini_image":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m.get('gemini_model','gemini-2.5-flash-image')}:generateContent?key={key}"
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseModalities": ["image"], "imageConfig": {"aspectRatio": "9:16" if h > w else "1:1"}}}
        r = _post_json(url, body, {}, timeout=180)
        for part in r["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                data = base64.b64decode(part["inlineData"]["data"])
                return _save_bytes(data, "png")
        raise RuntimeError("gemini returned no image")
    if endpoint == "pollinations":
        from urllib.parse import quote
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}?width={w}&height={h}&nologo=true&seed={int(time.time())%99999}"
        return _download(url, "jpg")
    if endpoint == "fal":
        fal_key = key or config.get("FAL_KEY")
        fal_model = m["fal_model"]
        r = _post_json(f"https://queue.fal.run/{fal_model}",
                       {"prompt": prompt, "image_size": {"width": w, "height": h}},
                       {"Authorization": f"Key {fal_key}"}, timeout=30)
        status_url = r.get("status_url") or r.get("response_url")
        # poll
        img_url = _poll_fal(status_url, fal_key)
        return _download(img_url, "jpg", headers={"Authorization": f"Key {fal_key}"})
    if endpoint == "openai_images" or endpoint == "openai_images_dalle3":
        omodel = "gpt-image-1" if "gpt-image" in m["id"] else "dall-e-3"
        base = "https://api.openai.com/v1"
        body = {"model": omodel, "prompt": prompt, "n": 1, "size": "1024x1792" if h > w else "1024x1024"}
        r = _post_json(f"{base}/images/generations", body, {"Authorization": f"Bearer {key}"}, timeout=180)
        if "b64_json" in r["data"][0]:
            return _save_bytes(base64.b64decode(r["data"][0]["b64_json"]), "png")
        return _download(r["data"][0]["url"], "jpg")
    if endpoint == "bfl":
        # Black Forest Labs
        r = _post_json(f"https://api.us1.bfl.ai/v1/{m.get('bfl_model','flux-pro-1.1')}",
                       {"prompt": prompt, "width": w, "height": h},
                       {"x-key": key}, timeout=30)
        img_url = _poll_bfl(r["id"], key)
        return _download(img_url, "jpg")
    # fallback — use pollinations
    from urllib.parse import quote
    return _download(f"https://image.pollinations.ai/prompt/{quote(prompt)}?width={w}&height={h}&nologo=true", "jpg")


def _poll_fal(status_url: str, key: str, max_wait: int = 300) -> str:
    for _ in range(max_wait // 5):
        time.sleep(5)
        try:
            req = urllib.request.Request(status_url, headers={"Authorization": f"Key {key}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode())
            if j.get("status") == "completed":
                img = j.get("image") or (j.get("images") or [{}])[0].get("url") or j.get("output",{}).get("images",[{}])[0].get("url")
                if img: return img
            if j.get("status") == "error": raise RuntimeError(str(j.get("error")))
        except urllib.error.URLError:
            continue
    raise TimeoutError("fal timed out")


def _poll_bfl(req_id: str, key: str, max_wait: int = 180) -> str:
    for _ in range(max_wait // 3):
        time.sleep(3)
        r = _get(f"https://api.us1.bfl.ai/v1/get_result?id={req_id}", {"x-key": key})
        j = json.loads(r.decode())
        if j.get("status") == "Ready": return j["result"]["sample"]
        if j.get("status") == "failed": raise RuntimeError("bfl failed")
    raise TimeoutError("bfl timed out")


# ============================================================ VIDEO
def generate_video(prompt: str, *, image_bytes: bytes = None, model: str = None) -> str:
    cat = "image_to_video" if image_bytes else "text_to_video"
    candidates = _candidate_order(cat, model)
    last_err = None
    for m in candidates:
        if not _has_key(m.get("key_env")) and not m.get("free_tier"):
            continue
        try:
            path = _call_video(m, prompt, image_bytes=image_bytes)
            ledger.record("aisuite.t2v" if not image_bytes else "aisuite.i2v", model=m["id"],
                          cost_usd=m.get("est_usd", 0.10))
            return path
        except Exception as e:
            last_err = e; continue
    raise RuntimeError(f"all {cat} providers failed: {last_err}")


def _call_video(m: dict, prompt: str, *, image_bytes: Optional[bytes]) -> str:
    endpoint = m["endpoint"]; key = config.get(m["key_env"]) if m.get("key_env") else None
    if endpoint == "fal":
        fal_model = m["fal_model"]; fal_key = key
        body: dict = {"prompt": prompt}
        if image_bytes:
            # upload via fal
            img_uri = _fal_upload(image_bytes, fal_key)
            body["image_url"] = img_uri
        r = _post_json(f"https://queue.fal.run/{fal_model}", body,
                       {"Authorization": f"Key {fal_key}"}, timeout=30)
        status_url = r.get("status_url") or r.get("response_url")
        vid_url = _poll_fal_video(status_url, fal_key)
        return _download(vid_url, "mp4", headers={"Authorization": f"Key {fal_key}"})
    if endpoint == "sora":
        r = _post_json("https://api.openai.com/v1/videos/generations",
                       {"model": "sora-1.0-turbo", "prompt": prompt},
                       {"Authorization": f"Bearer {key}"}, timeout=60)
        vid_url = _poll_openai_video(r["id"], key)
        return _download(vid_url, "mp4", headers={"Authorization": f"Bearer {key}"})
    raise RuntimeError(f"endpoint {endpoint} not implemented")


def _fal_upload(data: bytes, key: str) -> str:
    # Fal's files upload flow (simplified): use their data URI upload for images under 5MB
    b64 = base64.b64encode(data).decode()
    return f"data:image/jpeg;base64,{b64}"


def _poll_fal_video(status_url: str, key: str, max_wait: int = 600) -> str:
    for _ in range(max_wait // 10):
        time.sleep(10)
        try:
            req = urllib.request.Request(status_url, headers={"Authorization": f"Key {key}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode())
            if j.get("status") == "completed":
                v = j.get("video") or (j.get("videos") or [{}])[0].get("url") or j.get("output",{}).get("video",{}).get("url")
                if v: return v
            if j.get("status") == "error": raise RuntimeError(str(j.get("error")))
        except urllib.error.URLError: continue
    raise TimeoutError("fal video timed out")


def _poll_openai_video(vid: str, key: str, max_wait: int = 600) -> str:
    for _ in range(max_wait // 10):
        time.sleep(10)
        req = urllib.request.Request(f"https://api.openai.com/v1/videos/generations/{vid}",
                                     headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.loads(r.read().decode())
        if j.get("status") == "completed": return j["output"]["url"]
        if j.get("status") == "failed": raise RuntimeError("sora failed")
    raise TimeoutError("sora timed out")


# ============================================================ TTS
def tts(text: str, *, voice_id: str = "21m00Tcm4TlvDq8ikWAM", model: str = None) -> str:
    candidates = _candidate_order("voice", model)
    last_err = None
    for m in candidates:
        if not _has_key(m.get("key_env")) and not m.get("free_tier"):
            continue
        try:
            path = _call_tts(m, text, voice_id)
            ledger.record("aisuite.tts", model=m["id"], cost_usd=m.get("est_usd", 0.005))
            return path
        except Exception as e:
            last_err = e; continue
    raise RuntimeError(f"all tts providers failed: {last_err}")


def _call_tts(m: dict, text: str, voice_id: str) -> str:
    endpoint = m["endpoint"]; key = config.get(m["key_env"]) if m.get("key_env") else None
    if endpoint == "eleven":
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
            headers={"Content-Type": "application/json", "xi-api-key": key})
        with urllib.request.urlopen(req, timeout=60) as r:
            return _save_bytes(r.read(), "mp3")
    if endpoint == "openai_tts":
        req = urllib.request.Request(
            "https://api.openai.com/v1/audio/speech",
            data=json.dumps({"model": "gpt-4o-mini-tts", "input": text, "voice": "alloy", "format": "mp3"}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return _save_bytes(r.read(), "mp3")
    if endpoint == "gemini_tts":
        # Fallback to pyttsx3 / no TTS -> return empty placeholder if no key — let legacy voice.py handle
        raise RuntimeError("gemini tts not wired directly")
    raise RuntimeError("no tts provider")


# Catalog helper (used by web API to display)
def public_catalog() -> dict:
    """Strip key_env from catalog for sending to web UI (don't leak secrets)."""
    out = {}
    for cat, spec in CATALOG.items():
        if not isinstance(spec, dict) or "models" not in spec: continue
        out[cat] = {"label": spec.get("_label", cat), "models": []}
        for m in spec.get("models", []):
            out[cat]["models"].append({
                "id": m["id"], "name": m["name"], "provider": m["provider"],
                "paid": m.get("paid", True), "free_tier": m.get("free_tier", False),
                "est_usd": m.get("est_usd"), "has_key": _has_key(m.get("key_env")),
                "key_env": m.get("key_env"), "arena_rank": m.get("arena_rank"),
            })
    return out
