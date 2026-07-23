"""agentcore/costmode.py — v5.8.7 "never stop, degrade instead".

Founder mandate: "I want him always working even when he reaches the limit of
the paid APIs — he switches to the free ones."

Before v5.8.7 three separate things could bring the whole worker to a halt:

  1. daily budget spent   -> brain/grader refused to run AT ALL (even the free
                             council, which costs $0). Writer produced nothing.
  2. no_output_guard      -> flipped the hard kill switch. Full stop, human required.
  3. a paid provider 402  -> the call raised, the job failed, and the same dead
                             provider was retried on the next tick forever.

Now there is ONE authority for "what may I spend on right now":

    mode()                  'normal' | 'free_only'
    free_only()             True when paid calls are suspended
    may_spend(usd)          paid gate: budget + mode + kill switch
    usable(provider, paid)  per-provider gate: key + health + mode
    mark_error(provider, status, detail)   record 401/402/429 -> cooldown
    mark_ok(provider)       clear a provider's cooldown after a success
    degrade(reason, by)     switch to free_only instead of stopping

free_only is self-healing: it carries a `until` timestamp (default: next UTC
midnight, when the daily budget resets). After that the worker returns to
normal on its own. No human needed to un-stick production.

Provider cooldowns:
    402 / insufficient credits -> 12h cooldown, state 'out_of_credit'
    401 / 403 bad key          -> 24h cooldown, state 'dead_key'
    429 rate limited           -> 15m cooldown, state 'rate_limited'
A provider in cooldown is skipped by the router, so the next candidate (and
ultimately a free one) serves the request instead of the job failing.
"""
from __future__ import annotations
import os, time, datetime

_CACHE = {"t": 0.0, "mode": None, "health": None}
_TTL = 20.0            # seconds; keeps the hot path off the network

_COOLDOWN = {"out_of_credit": 12 * 3600, "dead_key": 24 * 3600, "rate_limited": 900}

# Which env var proves a provider is configured. Aliases allowed (first hit wins).
PROVIDER_KEYS = {
    "anthropic":  ["ANTHROPIC_API_KEY"],
    "openai":     ["OPENAI_API_KEY"],
    "gemini":     ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "groq":       ["GROQ_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "deepseek":   ["DEEPSEEK_API_KEY"],
    "mistral":    ["MISTRAL_API_KEY"],
    "xai":        ["XAI_API_KEY"],
    "together":   ["TOGETHER_API_KEY"],
    "fireworks":  ["FIREWORKS_API_KEY"],
    "cohere":     ["COHERE_API_KEY"],
    "fal":        ["FAL_KEY", "FAL_API_KEY"],
    "replicate":  ["REPLICATE_API_TOKEN"],
    "stability":  ["STABILITY_API_KEY"],
    "bfl":        ["BFL_API_KEY"],
    "ideogram":   ["IDEOGRAM_API_KEY"],
    "recraft":    ["RECRAFT_API_KEY"],
    "goapi":      ["GOAPI_KEY"],
    "elevenlabs": ["ELEVENLABS_API_KEY", "ELEVEN_API_KEY"],
    "cartesia":   ["CARTESIA_API_KEY"],
    "playht":     ["PLAYHT_API_KEY"],
    "deepgram":   ["DEEPGRAM_API_KEY"],
}

# Providers that never cost money -> always allowed, even in free_only.
FREE_PROVIDERS = {"gemini", "groq", "openrouter", "local", "edge-tts", "procedural"}


def has_key(provider: str) -> bool:
    for env in PROVIDER_KEYS.get(provider, [provider.upper() + "_API_KEY"]):
        if os.environ.get(env):
            return True
    return False


def _sb():
    try:
        from agentcore import runtime
        return runtime.supabase()
    except Exception:
        try:
            from agent import config as _c
            from supabase import create_client
            return create_client(_c.get("SUPABASE_URL"), _c.get("SUPABASE_SERVICE_KEY")
                                 or _c.get("SUPABASE_SERVICE_ROLE_KEY"))
        except Exception:
            return None


def _tenant():
    try:
        from agentcore import config as _cfg
        return _cfg.TENANT_ID
    except Exception:
        return os.environ.get("TENANT_ID", "me")


def _load(force: bool = False):
    now = time.time()
    if not force and (now - _CACHE["t"]) < _TTL and _CACHE["mode"] is not None:
        return
    mode, health = {"mode": "normal"}, {}
    sb = _sb()
    if sb is not None:
        try:
            rows = (sb.table("settings").select("key,value")
                    .in_("key", ["cost_mode", "provider_health"]).execute().data) or []
            for r in rows:
                if r["key"] == "cost_mode":
                    mode = r.get("value") or mode
                elif r["key"] == "provider_health":
                    health = (r.get("value") or {}).get("providers", {}) or {}
        except Exception:
            pass
    # free_only expires on its own -> the worker recovers without a human
    if mode.get("mode") == "free_only":
        until = float(mode.get("until") or 0)
        if until and time.time() > until:
            mode = {"mode": "normal", "recovered_from": mode.get("reason", "")}
            _write_mode(mode)
    _CACHE.update({"t": now, "mode": mode, "health": health})


def _write_mode(mode: dict):
    sb = _sb()
    if sb is None:
        return
    try:
        sb.table("settings").upsert(
            {"tenant_id": _tenant(), "key": "cost_mode", "value": mode},
            on_conflict="tenant_id,key").execute()
    except Exception:
        pass
    _CACHE["mode"] = mode


def _next_utc_midnight() -> float:
    d = datetime.datetime.now(datetime.timezone.utc)
    nxt = (d + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.timestamp()


def mode() -> str:
    _load()
    return (_CACHE["mode"] or {}).get("mode", "normal")


def free_only() -> bool:
    return mode() == "free_only"


def degrade(reason: str, by: str = "system", hours: float = None) -> None:
    """Suspend PAID calls but keep the worker running on free providers.
    This replaces 'stop everything' as the response to money problems."""
    until = (time.time() + hours * 3600) if hours else _next_utc_midnight()
    _write_mode({"mode": "free_only", "reason": reason, "by": by,
                 "since": time.time(), "until": until})


def restore(by: str = "human") -> None:
    _write_mode({"mode": "normal", "by": by, "since": time.time()})


def may_spend(usd: float) -> bool:
    """The single gate for spending real money. Free work never asks this."""
    if free_only():
        return False
    try:
        from agentcore import ledger
        if not ledger.budget_ok(usd):
            degrade(f"daily budget reached (needed ${usd:.3f})", by="budget_guard")
            return False
    except Exception:
        pass
    return True


def provider_state(provider: str) -> str:
    """'ok' | 'no_key' | 'out_of_credit' | 'dead_key' | 'rate_limited'"""
    if not has_key(provider) and provider not in FREE_PROVIDERS:
        return "no_key"
    _load()
    h = (_CACHE["health"] or {}).get(provider) or {}
    st, until = h.get("state"), float(h.get("cooldown_until") or 0)
    if st and st != "ok" and until > time.time():
        return st
    return "ok"


def usable(provider: str, paid: bool = True) -> bool:
    """Ask before routing a call to a provider."""
    if paid and provider not in FREE_PROVIDERS and free_only():
        return False
    return provider_state(provider) == "ok"


def _classify(status: int, detail: str) -> str:
    d = (detail or "").lower()
    if status == 402 or "insufficient" in d or "quota" in d or "credit" in d or "billing" in d:
        return "out_of_credit"
    if status in (401, 403) or "invalid api key" in d or "unauthorized" in d:
        return "dead_key"
    if status == 429 or "rate limit" in d:
        return "rate_limited"
    return ""


def mark_error(provider: str, status: int = 0, detail: str = "") -> str:
    """Record a provider failure. Returns the state applied ('' = transient)."""
    state = _classify(status, detail)
    if not state:
        return ""
    sb = _sb()
    _load(force=True)
    health = dict(_CACHE["health"] or {})
    health[provider] = {"state": state, "detail": (detail or "")[:200],
                        "at": time.time(),
                        "cooldown_until": time.time() + _COOLDOWN[state]}
    if sb is not None:
        try:
            sb.table("settings").upsert(
                {"tenant_id": _tenant(), "key": "provider_health",
                 "value": {"providers": health, "updated_at": time.time()}},
                on_conflict="tenant_id,key").execute()
        except Exception:
            pass
    _CACHE["health"] = health
    return state


def mark_ok(provider: str) -> None:
    """A successful call clears a stale cooldown."""
    _load()
    health = dict(_CACHE["health"] or {})
    if provider in health and health[provider].get("state") not in (None, "ok"):
        health[provider] = {"state": "ok", "at": time.time(), "cooldown_until": 0}
        sb = _sb()
        if sb is not None:
            try:
                sb.table("settings").upsert(
                    {"tenant_id": _tenant(), "key": "provider_health",
                     "value": {"providers": health, "updated_at": time.time()}},
                    on_conflict="tenant_id,key").execute()
            except Exception:
                pass
        _CACHE["health"] = health


# ======================================================================
# v5.8.8 SPEND POLICY — founder mandate, 2026-07-23
#
#   "Paid money is consumed ONLY on art creation. Nothing on strategy.
#    Once every 10 days Anthropic reviews the period and trains the agents.
#    Free open models debate everything else."
#
# Enforced here so no department can quietly opt out.
#   thinking work (text/strategy/grading/writing) -> FREE providers only
#   art work      (image/video/voice)             -> paid allowed, budget-capped
#   the 10-day retro                              -> the ONE paid thinking call
# ======================================================================

ART_CATEGORIES = {"image", "video", "voice", "audio", "text_to_image",
                  "image_edit", "text_to_video", "image_to_video", "video_edit"}
THINKING_CATEGORIES = {"text", "strategy", "grading", "writing", "research", "chat"}

_POLICY_DEFAULT = {
    "paid_art": True,            # money may be spent making the actual asset
    "paid_thinking": False,      # money may NOT be spent thinking
    "strategy_audit_days": 10,   # ...except once every N days, for the retro
}


def policy() -> dict:
    """settings.spend_policy, falling back to the founder default."""
    _load()
    sb = _sb()
    if sb is None:
        return dict(_POLICY_DEFAULT)
    try:
        row = (sb.table("settings").select("value").eq("key", "spend_policy")
               .limit(1).execute().data)
        if row:
            p = dict(_POLICY_DEFAULT)
            p.update(row[0].get("value") or {})
            return p
    except Exception:
        pass
    return dict(_POLICY_DEFAULT)


def may_spend_on(category: str, usd: float, *, override: bool = False) -> bool:
    """The category-aware spend gate. `override=True` is reserved for the
    scheduled strategy audit — the only paid thinking allowed by policy."""
    cat = (category or "").lower()
    p = policy()
    if cat in THINKING_CATEGORIES and not override and not p.get("paid_thinking", False):
        return False                      # strategy is free-models-only, always
    if cat in ART_CATEGORIES and not p.get("paid_art", True):
        return False
    return may_spend(usd)


def audit_due() -> bool:
    """True when the N-day Anthropic strategy retro should run."""
    p = policy()
    days = float(p.get("strategy_audit_days", 10) or 10)
    sb = _sb()
    if sb is None:
        return False
    try:
        row = (sb.table("settings").select("value").eq("key", "last_strategy_audit")
               .limit(1).execute().data)
        last = float(((row or [{}])[0].get("value") or {}).get("at") or 0)
    except Exception:
        last = 0
    return (time.time() - last) >= days * 86400


def mark_audit_done(summary: str = "") -> None:
    sb = _sb()
    if sb is None:
        return
    try:
        sb.table("settings").upsert(
            {"tenant_id": _tenant(), "key": "last_strategy_audit",
             "value": {"at": time.time(), "summary": summary[:2000]}},
            on_conflict="tenant_id,key").execute()
    except Exception:
        pass
