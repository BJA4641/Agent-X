"""departments/providers.py — v5.8.7 provider probe.

Answers, with evidence rather than assumption:
    "which AI providers are linked, which are alive, and how much credit is left?"

HONEST LIMITATION — most vendors do NOT expose a balance endpoint.
Verified July 2026:

  BALANCE AVAILABLE (real endpoint, real number)
    openrouter   GET /api/v1/credits          total_credits - total_usage  -> USD
    deepseek     GET /user/balance            total_balance                -> USD
    elevenlabs   GET /v1/user/subscription    character_limit - used       -> characters
    stability    GET /v1/user/balance         credits                      -> credits
    goapi        GET /api/v1/user             (account object, best effort)

  NO BALANCE API — key can be validated, balance must be read on their dashboard
    openai       (confirmed: no public balance endpoint; the old
                  /dashboard/billing/credit_grants is gone)
    anthropic    (no balance endpoint)
    gemini       (free tier; quota not exposed via API)
    groq         (free tier; no balance endpoint)
    fal, bfl, ideogram, recraft, replicate, cartesia, playht, deepgram

For "no balance API" providers we still probe a cheap authenticated GET so the
dashboard can say linked / dead key / unreachable truthfully, and we surface
our own measured spend from run_ledger as the usable cost signal.

Nothing here is invented: if a probe fails we store the error, not a guess.
"""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error

from agentcore import Worker, Job, AgentContext, Priority
from agentcore import costmode

TIMEOUT = 12

# provider -> (url, auth_header_builder, kind, parser_name)
#   kind: 'balance_usd' | 'balance_units' | 'validate'
PROBES = {
    "openrouter": ("https://openrouter.ai/api/v1/credits",
                   lambda k: {"Authorization": f"Bearer {k}"}, "balance_usd", "openrouter"),
    "deepseek":   ("https://api.deepseek.com/user/balance",
                   lambda k: {"Authorization": f"Bearer {k}"}, "balance_usd", "deepseek"),
    "elevenlabs": ("https://api.elevenlabs.io/v1/user/subscription",
                   lambda k: {"xi-api-key": k}, "balance_units", "elevenlabs"),
    "stability":  ("https://api.stability.ai/v1/user/balance",
                   lambda k: {"Authorization": f"Bearer {k}"}, "balance_units", "stability"),
    "openai":     ("https://api.openai.com/v1/models",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    "anthropic":  ("https://api.anthropic.com/v1/models",
                   lambda k: {"x-api-key": k, "anthropic-version": "2023-06-01"}, "validate", None),
    "groq":       ("https://api.groq.com/openai/v1/models",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    "gemini":     ("https://generativelanguage.googleapis.com/v1beta/models",
                   lambda k: {"x-goog-api-key": k}, "validate", None),
    "mistral":    ("https://api.mistral.ai/v1/models",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    "together":   ("https://api.together.xyz/v1/models",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    "xai":        ("https://api.x.ai/v1/models",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    "fireworks":  ("https://api.fireworks.ai/inference/v1/models",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    "replicate":  ("https://api.replicate.com/v1/account",
                   lambda k: {"Authorization": f"Bearer {k}"}, "validate", None),
    # fal has no documented status endpoint; the queue root answers auth
    # correctly (401 for a bad key, 4xx-but-authenticated otherwise).
    "fal":        ("https://queue.fal.run/fal-ai/flux/schnell/requests/status",
                   lambda k: {"Authorization": f"Key {k}"}, "validate", None),
    "deepgram":   ("https://api.deepgram.com/v1/projects",
                   lambda k: {"Authorization": f"Token {k}"}, "validate", None),
}

# What each provider is actually wired to do inside Agent-X.
ROLE = {
    "gemini": "text (free council) + images", "groq": "text (free council)",
    "openrouter": "text (free council + paid overflow)", "anthropic": "final audit only",
    "openai": "text fallback + images", "deepseek": "text (cheap reasoning)",
    "fal": "video + images", "bfl": "images (FLUX)", "ideogram": "images with text",
    "recraft": "vector / illustration images", "goapi": "images (Midjourney)",
    "stability": "images (SD)", "replicate": "images / video",
    "elevenlabs": "premium voice", "cartesia": "voice", "playht": "voice",
    "deepgram": "voice / transcription", "mistral": "text", "xai": "text",
    "together": "text", "fireworks": "text", "cohere": "text",
}


def _key(provider: str) -> str:
    for env in costmode.PROVIDER_KEYS.get(provider, []):
        v = os.environ.get(env)
        if v:
            return v
    return ""


UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")

def _get(url: str, headers: dict):
    # v5.9.1: several vendors (groq via Cloudflare) reject urllib's default
    # User-Agent with code 1010 and we reported it as a dead key.
    headers = {"User-Agent": UA, "Accept": "application/json", **(headers or {})}
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read().decode("utf-8", "replace")


def _parse(name: str, body: str):
    """-> (amount, unit, extra) or (None, None, {}) if the shape was unexpected."""
    try:
        d = json.loads(body)
    except Exception:
        return None, None, {}
    try:
        if name == "openrouter":
            d = d.get("data", d)
            tot, used = float(d.get("total_credits") or 0), float(d.get("total_usage") or 0)
            return round(tot - used, 4), "USD", {"granted": tot, "used": used}
        if name == "deepseek":
            infos = d.get("balance_infos") or []
            if infos:
                return round(float(infos[0].get("total_balance") or 0), 4), \
                       (infos[0].get("currency") or "USD"), {"available": d.get("is_available")}
        if name == "elevenlabs":
            lim, used = float(d.get("character_limit") or 0), float(d.get("character_count") or 0)
            return round(lim - used, 0), "characters", {"tier": d.get("tier"), "limit": lim}
        if name == "stability":
            return round(float(d.get("credits") or 0), 4), "credits", {}
    except Exception:
        pass
    return None, None, {}


def _extract_models(provider: str, body: str) -> list:
    """v5.9.1 — record which model IDs the vendor ACTUALLY serves today.

    The writer died with "council+fallback failed" while every key validated:
    the council was asking for `gemini-2.5-flash`, a name two generations stale.
    Hardcoded model IDs rot. Discover them instead."""
    try:
        d = json.loads(body)
    except Exception:
        return []
    out = []
    try:
        if provider == "gemini":
            for m in d.get("models", []):
                name = (m.get("name") or "").split("/")[-1]
                methods = m.get("supportedGenerationMethods") or m.get("supportedActions") or []
                if name and (not methods or "generateContent" in methods):
                    out.append(name)
        else:                                   # OpenAI-compatible /v1/models
            for m in d.get("data", []):
                if m.get("id"):
                    out.append(m["id"])
    except Exception:
        return []
    return sorted(set(out))[:120]


def probe_one(provider: str) -> dict:
    """Never raises. Returns a truthful record of what we could and could not learn."""
    key = _key(provider)
    role = ROLE.get(provider, "")
    if not key:
        return {"provider": provider, "linked": False, "status": "no_key",
                "balance": None, "unit": None, "role": role,
                "note": "no API key set in Railway"}
    spec = PROBES.get(provider)
    if not spec:
        return {"provider": provider, "linked": True, "status": "linked",
                "balance": None, "unit": None, "role": role,
                "note": "key present; this vendor has no public status or balance endpoint"}
    url, hdr, kind, parser = spec
    try:
        code, body = _get(url, hdr(key))
        amount, unit, extra = (_parse(parser, body) if parser else (None, None, {}))
        models = _extract_models(provider, body)
        costmode.mark_ok(provider)
        rec = {"provider": provider, "linked": True, "status": "ok", "http": code,
               "balance": amount, "unit": unit, "role": role, "extra": extra,
               "models": models}
        if kind == "validate":
            rec["note"] = "key valid — vendor exposes no balance endpoint, check their dashboard"
        elif amount is None:
            rec["note"] = "key valid — balance endpoint answered in an unexpected shape"
        else:
            rec["note"] = "live balance"
        if amount is not None and amount <= 0:
            rec["status"] = "out_of_credit"
        return rec
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        # v5.9.1: DO NOT call costmode.mark_error here. The probe is diagnostic;
        # a wrong endpoint or a Cloudflare block would otherwise cooldown a
        # perfectly good provider for 24h and silently shrink the free council.
        # Only real production call failures (aisuite/council) set cooldowns.
        state = costmode._classify(e.code, detail)
        if state == "dead_key" and "permission" in (detail or "").lower():
            state = "needs_scope"      # key works, token just lacks a read scope
        return {"provider": provider, "linked": True, "status": state or f"http_{e.code}",
                "http": e.code, "balance": None, "unit": None, "role": role,
                "note": (detail or str(e))[:180]}
    except Exception as e:
        return {"provider": provider, "linked": True, "status": "unreachable",
                "balance": None, "unit": None, "role": role, "note": str(e)[:180]}


def _publish_ladder(sb, bus, job):
    """v5.9.9 REQ-LADDER-OBS — settings.free_ladder_report. The whole
    zero-output outage came down to "which free rungs are actually usable",
    and there was no way to see it without reading job error strings."""
    try:
        from agentcore.council import ladder_report
        rep = ladder_report()
        try:
            from agentcore import ratelimit as _rl
            rep["rate_limits"] = _rl.snapshot()
        except Exception:
            pass
        sb.table("settings").upsert(
            {"tenant_id": os.environ.get("TENANT_ID", "me"),
             "key": "free_ladder_report", "value": rep},
            on_conflict="tenant_id,key").execute()
        if rep.get("below_floor"):
            bus.agent("cto", f"⚠️ free ladder below floor — only {rep.get('usable_count')} usable rung(s). "
                             f"dropped: {'; '.join(rep.get('dropped') or [])[:200]}",
                      "warn", "ladder_below_floor", job_id=getattr(job, "id", None))
        else:
            bus.agent("cto", f"🪜 free ladder: {rep.get('usable_count')} usable rung(s) — "
                             f"{', '.join(rep.get('usable') or [])[:180]}",
                      "info", "ladder_ok", job_id=getattr(job, "id", None))
    except Exception:
        pass


def probe(w: Worker, job: Job, ctx: AgentContext):
    """providers.probe — refresh linked/alive/balance for every known provider."""
    _bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    results, checked = {}, 0
    for provider in costmode.PROVIDER_KEYS:
        rec = probe_one(provider)
        results[provider] = rec
        if rec.get("linked"):
            checked += 1

    # our own measured spend per provider today (the number that actually matters)
    spend = {}
    if sb is not None:
        try:
            import datetime as _dt
            today = _dt.date.today().isoformat()
            rows = (sb.table("run_ledger").select("model,cost_usd")
                    .gte("created_at", today).execute().data) or []
            for r in rows:
                m = (r.get("model") or "").lower()
                for p in costmode.PROVIDER_KEYS:
                    if p in m or (p == "anthropic" and "claude" in m) or \
                       (p == "openai" and ("gpt" in m or m.startswith("o3"))) or \
                       (p == "gemini" and "gemini" in m) or (p == "groq" and "llama" in m):
                        spend[p] = round(spend.get(p, 0) + float(r.get("cost_usd") or 0), 4)
                        break
        except Exception:
            pass
    for p, rec in results.items():
        rec["spend_today_usd"] = spend.get(p, 0.0)

    if sb is not None:
        try:
            sb.table("settings").upsert(
                {"tenant_id": _tenant(), "key": "provider_status",
                 "value": {"providers": results, "checked_at": time.time(),
                           "cost_mode": costmode.mode()}},
                on_conflict="tenant_id,key").execute()
        except Exception:
            pass

    # v5.9.1: publish the live model list so the council stops guessing names.
    catalog = {p: r.get("models") or [] for p, r in results.items() if r.get("models")}
    if sb is not None and catalog:
        try:
            sb.table("settings").upsert(
                {"tenant_id": _tenant(), "key": "provider_models",
                 "value": {"models": catalog, "checked_at": time.time()}},
                on_conflict="tenant_id,key").execute()
        except Exception:
            pass

    linked = [p for p, r in results.items() if r.get("linked")]
    broke = [p for p, r in results.items() if r.get("status") in ("out_of_credit", "dead_key")]
    with_bal = {p: f"{r['balance']} {r['unit']}" for p, r in results.items()
                if r.get("balance") is not None}
    msg = f"🔌 provider probe — {len(linked)} linked"
    if with_bal:
        msg += " · balances: " + ", ".join(f"{p} {v}" for p, v in sorted(with_bal.items()))
    if broke:
        msg += " · ⚠️ needs attention: " + ", ".join(broke)
    _bus.agent("cfo", msg, "warn" if broke else "info", "provider_probe", job_id=job.id)

    # reschedule (every 6h) so the dashboard stays current without a human
    try:
        w.queue.enqueue(Job(job_type="providers.probe", payload={"scheduled": True},
                            priority=Priority.LOW, scheduled_for=time.time() + 6 * 3600,
                            idempotency_key=f"probe:{int(time.time() // (6 * 3600))}"))
    except Exception:
        pass
    try:
        _publish_ladder(sb, _bus, job)
    except Exception:
        pass
    w.queue.complete(job, {"ok": True, "linked": len(linked), "checked": checked,
                           "balances": with_bal, "attention": broke})


def _tenant():
    try:
        from agentcore import config as _cfg
        return _cfg.TENANT_ID
    except Exception:
        return os.environ.get("TENANT_ID", "me")


def register(w: Worker):
    w.register("providers.probe", probe)

