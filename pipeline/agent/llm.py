"""llm.py — one door to every text model, switchable from the Studio without redeploy.

v5.5 P0 FIX: primary path now routes through agentcore.aisuite (catalog-driven, 74 models),
falling back to legacy direct-provider code ONLY if aisuite throws (misconfigured catalog,
missing deps, etc). This makes the /dashboard/models model picker actually control inference.
"""
import os
import json, time, urllib.request, urllib.error, traceback
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

def chat(prompt: str, max_tokens: int = 800, tier: str = None):
    """-> (text, cost_usd, model_label).

    v5.5: TRY AISUITE FIRST (unified router, honors /dashboard/models selection),
    fall back to legacy direct-provider rotation only if aisuite raises. This
    way the model picker actually works, but a bad catalog entry never halts
    production.
    """
    # 1) aisuite path (v5.5+)
    try:
        from agentcore import aisuite
        chosen, model_override = selection()
        # Map chosen provider -> aisuite tier hint
        # v5.10.8 REQ-CHEAP-TEXT (DEC-048): writing a 7-beat reel script is a
        # commodity text task, not a reasoning task. Today it ran on
        # claude-sonnet-4-5 at $0.029/call — 50 calls, $1.46, while $0.00 went to
        # images, video or voice. The money must follow the CONTENT, not the chat.
        # Callers may request a tier explicitly; otherwise cheap is the default and
        # premium must be asked for by name.
        tier = tier or os.environ.get("TEXT_TIER_DEFAULT", "cheap")
        text, meta = aisuite.generate_text(prompt, tier=tier, model=model_override or None,
                                           max_tokens=max_tokens)
        if text:
            return text, float(meta.get("cost_usd", 0.0)), meta.get("model", "aisuite")
    except Exception as e:
        # Log but don't raise — fall through to legacy path
        try:
            traceback.print_exc()
        except Exception:
            pass

    # 2) Legacy direct-provider fallback (v5.3 code)
    return _chat_legacy(prompt, max_tokens=max_tokens)


def _chat_legacy(prompt: str, max_tokens: int = 800):
    """Original v5.3 provider rotation (Anthropic/Gemini/Groq/OpenRouter)."""
    chosen, model = selection()
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
    """v5.11.21 REQ-PROVIDER-HEALTH-TEXT (DEC-073): this is the single choke
    point every text call passes through (council drafts, judges, free_chat,
    paid chat) — so it is the ONE correct place to report provider health.

    Before this, only the image suite (aisuite.py) ever called
    costmode.mark_error. The text path raised raw urllib HTTPErrors: a groq
    key rotated at the provider returned 403 on EVERY call for 10+ hours while
    settings.free_ladder_report kept saying "usable" — because nothing told
    costmode. A dead rung that reports healthy is worse than no rung: the
    council kept spending its two draft slots on it (see council.py DEC-073).

    On HTTP error: classify + cooldown via costmode.mark_error (403→dead_key,
    429→rate_limited, 402→out_of_credit) and re-raise with provider/model/status
    in the message so operators see "groq/llama-3.3-70b: HTTP 403" instead of
    a bare urllib traceback. On success: mark_ok clears any stale cooldown.
    """
    try:
        out = _call_raw(prov, model, prompt, max_tokens)
        try:
            from agentcore import costmode as _cm
            _cm.mark_ok(prov)
        except Exception:
            pass
        return out
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = (e.read() or b"").decode("utf-8", "replace")[:300]
        except Exception:
            pass
        try:
            from agentcore import costmode as _cm
            _cm.mark_error(prov, int(e.code), body or str(e))
        except Exception:
            pass
        raise RuntimeError(
            f"{prov}/{model}: HTTP {e.code} {e.reason}"
            + (f" — {body[:160]}" if body else "")) from None


def _call_raw(prov, model, prompt, max_tokens):
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
        # v5.9.2: Gemini 2.5+ THINKS by default and the reasoning tokens come out
        # of maxOutputTokens. With a small budget the model spends it all thinking,
        # returns finishReason=MAX_TOKENS and a candidate with NO "parts" key —
        # the old line then died on KeyError and the council reported only
        # "council+fallback failed". Disable thinking for drafting work and give
        # the answer real headroom.
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max(max_tokens, 2048),
                "temperature": 0.9,
                "thinkingConfig": {"thinkingBudget": 0},
            },
        }
        try:
            data = _post(url, body, {})
        except Exception as e:
            # thinkingConfig is rejected by older models -> retry without it
            body["generationConfig"].pop("thinkingConfig", None)
            data = _post(url, body, {})
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError(f"gemini {model}: no candidates "
                               f"({str(data.get('promptFeedback'))[:120]})")
        cand = cands[0]
        parts = ((cand.get("content") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts)
        if not text.strip():
            raise RuntimeError(f"gemini {model}: empty text "
                               f"(finishReason={cand.get('finishReason')})")
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
