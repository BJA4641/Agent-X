"""llm.py — one door to every text model, switchable from the Studio without redeploy.

Providers:
  anthropic  — Claude (paid, highest quality; ~$3/M in, $15/M out)
  gemini     — Google Gemini 2.5 Flash text (FREE tier; key already used for images)
  openrouter — 100+ models incl. moonshotai/kimi-k2:free (FREE)
  groq       — Llama 3.3 70B (FREE tier, very fast)

Selection order: settings table row {key:"model"} (set from the Studio) -> env MODEL_PROVIDER.
If the chosen provider's key is missing or the call fails, falls through the rest so a
misconfigured picker can never halt the factory.
"""
import json, time, urllib.request
from . import config

DEFAULT_MODEL = {
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-2.5-flash",
    "openrouter": "moonshotai/kimi-k2:free",
    "groq": "llama-3.3-70b-versatile",
}
FREE = {"gemini", "openrouter", "groq"}  # cost recorded as 0 on free tiers

_cache = {"at": 0.0, "provider": None, "model": None}

def _db_setting():
    if not config.HAS_SUPABASE:
        return {}
    try:
        from supabase import create_client
        sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
        r = sb.table("settings").select("value").eq("tenant_id", config.TENANT_ID).eq("key", "model").execute().data
        return (r[0]["value"] or {}) if r else {}
    except Exception:
        return {}

def selection():
    now = time.time()
    if now - _cache["at"] > 60:
        v = _db_setting()
        _cache.update(at=now,
                      provider=v.get("provider") or config.get("MODEL_PROVIDER", "anthropic"),
                      model=v.get("model") or config.get("MODEL_NAME", ""))
    return _cache["provider"], _cache["model"]

def _has_key(p):
    return bool({"anthropic": config.get("ANTHROPIC_API_KEY"), "gemini": config.get("GEMINI_API_KEY"),
                 "openrouter": config.get("OPENROUTER_API_KEY"), "groq": config.get("GROQ_API_KEY")}.get(p))

def ready() -> bool:
    return any(_has_key(p) for p in DEFAULT_MODEL)

def chat(prompt: str, max_tokens: int = 800):
    """-> (text, cost_usd, model_label). Tries chosen provider, then falls through the rest.

    Auto-fallback is driven by the 'model' settings row's auto_fallback flag. When OFF,
    only the chosen provider is tried (useful when you want to force-debug a specific
    model). When ON (default), it rotates through all working providers so production
    never stops because of one dead wallet/key.
    """
    chosen, model = selection()
    # Read auto_fallback flag — default ON.
    auto_fb = True
    try:
        if config.HAS_SUPABASE:
            from supabase import create_client
            sb2 = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
            r2 = sb2.table("settings").select("value").eq("tenant_id", config.TENANT_ID).eq("key", "model").execute().data
            if r2 and isinstance(r2[0].get("value"), dict):
                auto_fb = r2[0]["value"].get("auto_fallback", True) is not False
    except Exception:
        auto_fb = True

    if auto_fb:
        order = [chosen] + [p for p in ["anthropic", "gemini", "groq", "openrouter"] if p != chosen]
    else:
        order = [chosen]
    last = None
    for prov in order:
        if not _has_key(prov):
            continue
        try:
            m = model if prov == chosen and model else DEFAULT_MODEL[prov]
            return _call(prov, m, prompt, max_tokens)
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"no LLM provider succeeded: {last}")

def _call(prov, model, prompt, max_tokens):
    if prov == "anthropic":
        import anthropic
        msg = anthropic.Anthropic().messages.create(model=model, max_tokens=max_tokens,
                                                    messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content if b.type == "text")
        cost = (msg.usage.input_tokens * 3 + msg.usage.output_tokens * 15) / 1e6
        return text, cost, msg.model
    if prov == "gemini":
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
               f"?key={config.get('GEMINI_API_KEY')}")
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": max_tokens}}
        data = _post(url, body, {})
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        return text, 0.0, f"gemini:{model}"
    if prov == "openrouter":
        data = _post("https://openrouter.ai/api/v1/chat/completions",
                     {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
                     {"Authorization": f"Bearer {config.get('OPENROUTER_API_KEY')}"})
        text = data["choices"][0]["message"]["content"]
        return text, 0.0 if model.endswith(":free") else 0.0, f"openrouter:{model}"
    if prov == "groq":
        data = _post("https://api.groq.com/openai/v1/chat/completions",
                     {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
                     {"Authorization": f"Bearer {config.get('GROQ_API_KEY')}"})
        text = data["choices"][0]["message"]["content"]
        return text, 0.0, f"groq:{model}"
    raise ValueError(prov)

def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())
