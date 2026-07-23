"""agentcore/council.py — v5.8.2 free-first model council.

Cost architecture (founder mandate: "use the free tools, make them debate,
verify in the end with Claude so we spend less"):

  DRAFT      free model A writes a candidate            → $0
  DRAFT      free model B writes a second candidate     → $0
  DEBATE     a free model critiques both and merges the
             strongest elements into ONE final output   → $0
  VERIFY     the CQO grader (Claude, agent/grader.py)
             judges the final output                    → 1 paid call

Claude is never called here. Paid spend per item collapses from
write+rewrites+grade (4-6 paid calls) to exactly one grade call.

Free providers used (whichever keys exist), in order:
  groq        llama-3.3-70b-versatile        (free tier)
  openrouter  moonshotai/kimi-k2:free        (free route)
  gemini      gemini-2.5-flash               (generous free tier)

Env:
  COUNCIL_MODE=0   disables the council (falls straight back to llm.chat)

Public API:
  free_chat(prompt, max_tokens)      → (text, 0.0, label)  single free call
  debate(prompt, max_tokens)         → (text, 0.0, label)  full 3-step debate
  debate_or_chat(prompt, max_tokens) → council if possible, llm.chat otherwise
"""
from __future__ import annotations
import os, time, traceback

# Free provider order: (provider_key_in_agent_llm, model)
_FREE_ORDER = [
    # v5.8.8 — verified live against openrouter /api/v1/models on 2026-07-23 and
    # ranked against arena.ai open-weight leaderboard. The old entry here
    # ("moonshotai/kimi-k2:free") NO LONGER EXISTS as a free route, which is why
    # openrouter drafts kept failing and the writer fell through to paid Claude.
    ("gemini",     "gemini-2.5-flash"),                    # free tier, most generous
    ("groq",       "llama-3.3-70b-versatile"),             # free tier, fastest
    ("openrouter", "google/gemma-4-31b-it:free"),          # Apache-2.0, arena top-10 open weight
    ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("openrouter", "openai/gpt-oss-20b:free"),
]

# v5.9.1 — resolve model names against what the vendor ACTUALLY serves.
# providers.probe writes settings.provider_models with the live ID list; we
# match our preference by prefix so "gemini-2.5-flash" gracefully becomes
# whatever flash model exists today instead of failing every single draft.
_PREF = {
    "gemini":     ["flash-latest", "3.6-flash", "3-flash", "2.5-flash", "flash"],
    "groq":       ["llama-3.3-70b", "llama-3.1-70b", "llama-4", "llama"],
    "openrouter": [":free"],
}

def _live_models():
    # v5.9.3: this used an undefined runtime helper — the AttributeError was
    # swallowed, so model discovery silently never applied.
    try:
        from agentcore import costmode as _cm
        sb = _cm._sb()
        if sb is None:
            return {}
        row = (sb.table("settings").select("value").eq("key", "provider_models")
               .limit(1).execute().data)
        return ((row or [{}])[0].get("value") or {}).get("models") or {}
    except Exception:
        return {}


def _resolve(provider: str, wanted: str, live: dict) -> str:
    """Return `wanted` if the vendor still serves it, else the best live match."""
    ids = live.get(provider) or []
    if not ids or wanted in ids:
        return wanted
    for frag in _PREF.get(provider, []):
        for mid in ids:
            if frag in mid:
                return mid
    return wanted            # nothing matched — let the call fail loudly


# Overridable from settings.free_council_models (written by strategy.arena_scout)
# so the roster follows the leaderboard without a redeploy.
def _order():
    try:
        from agentcore import costmode as _cm
        sb = _cm._sb()
        if sb is None:
            return _FREE_ORDER
        row = (sb.table("settings").select("value").eq("key", "free_council_models")
               .limit(1).execute().data)
        models = ((row or [{}])[0].get("value") or {}).get("models") or []
        picked = [(m["provider"], m["model"]) for m in models
                  if m.get("provider") and m.get("model")]
        if picked:
            return picked
    except Exception:
        pass
    return _FREE_ORDER

_CRITIQUE_INSTRUCTIONS = (
    "You are a ruthless senior editor for short-form social content. Below is an "
    "ORIGINAL TASK and {k} CANDIDATE response(s) to it, produced by different "
    "writers. Your job:\n"
    "1. Judge each candidate: hook strength, specificity, pacing, honesty "
    "(no hype, no income claims), and whether it follows the task format EXACTLY.\n"
    "2. Produce ONE final response that keeps the strongest elements and fixes "
    "every weakness you found.\n"
    "3. Output ONLY the final response, in EXACTLY the output format the "
    "original task demands (if the task demands JSON, output only that JSON — "
    "no commentary, no markdown fences).\n"
)


def _providers():
    """Free providers with a key, not in cooldown, resolved to a LIVE model id."""
    from agent import llm as _llm
    live = _live_models()
    out = []
    for (p, m) in _order():
        m = _resolve(p, m, live)
        if not _llm._has_key(p):
            continue
        try:
            from agentcore import costmode as _cm
            if _cm.provider_state(p) not in ("ok",):
                continue          # rate-limited / dead key -> try the next free one
        except Exception:
            pass
        out.append((p, m))
    return out


def enabled() -> bool:
    return os.environ.get("COUNCIL_MODE", "1") != "0" and len(_providers()) >= 1


def _call_free(prov: str, model: str, prompt: str, max_tokens: int):
    """One raw free-provider call via the existing adapter. Returns text or raises."""
    from agent import llm as _llm
    text, _cost, label = _llm._call(prov, model, prompt, max_tokens)
    if not (text or "").strip():
        raise RuntimeError(f"{prov} returned empty text")
    return text, label


def free_chat(prompt: str, max_tokens: int = 800):
    """Single free-model call with rotation across free providers on failure.
    Returns (text, 0.0, label). Raises RuntimeError if no free provider works.

    v5.9.2: the old version kept only the LAST exception, so a three-provider
    failure surfaced as one opaque line and cost hours of guesswork. Every
    provider's own error is now reported."""
    provs = _providers()
    if not provs:
        raise RuntimeError("no free provider configured (need GEMINI/GROQ/OPENROUTER key "
                           "with a usable state)")
    errors = []
    for prov, model in provs:
        try:
            text, label = _call_free(prov, model, prompt, max_tokens)
            return text, 0.0, f"free:{label}"
        except Exception as e:
            errors.append(f"{prov}/{model}: {str(e)[:160]}")
            continue
    detail = " | ".join(errors)
    _report_council_failure(detail)
    raise RuntimeError(f"no free provider available -> {detail}")


def _report_council_failure(detail: str):
    """Write the per-provider reasons where a human can actually see them.
    v5.9.3: previously called two runtime helpers that were never defined, so
    every report vanished into an except block. Uses costmode._sb() now."""
    print(f"[council] ALL FREE MODELS FAILED -> {detail}")
    try:
        from agentcore import costmode as _cm
        sb = _cm._sb()
        if sb is not None:
            sb.table("settings").upsert(
                {"tenant_id": _cm._tenant(), "key": "council_last_failure",
                 "value": {"at": time.time(), "detail": detail[:1200]}},
                on_conflict="tenant_id,key").execute()
    except Exception as e:
        print(f"[council] could not record failure: {e}")


def debate(prompt: str, max_tokens: int = 1800):
    """Full council: 2 free drafts → free critique/merge → final text.
    Degrades gracefully: 1 provider → draft + self-critique pass.
    Returns (text, 0.0, label)."""
    provs = _providers()
    if not provs:
        _report_council_failure("no usable free provider (check keys and cooldowns)")
        raise RuntimeError("council: no free providers configured")

    t0 = time.time()
    candidates = []           # [(label, text)]
    draft_errors = []
    for prov, model in provs[:2]:
        try:
            text, label = _call_free(prov, model, prompt, max_tokens)
            candidates.append((label, text))
        except Exception as e:
            draft_errors.append(f"{prov}/{model}: {str(e)[:160]}")
            traceback.print_exc()
            continue
    if not candidates:
        detail = " | ".join(draft_errors) if draft_errors else "no providers"
        _report_council_failure(detail)
        raise RuntimeError(f"council: all free drafts failed -> {detail}")

    # Judge/merger = a provider different from candidate A when possible.
    judge_pool = provs[1:] + provs[:1]
    header = _CRITIQUE_INSTRUCTIONS.format(k=len(candidates))
    cand_block = "\n\n".join(
        f"--- CANDIDATE {i+1} (by {lab}) ---\n{txt[:6000]}"
        for i, (lab, txt) in enumerate(candidates))
    critique_prompt = (f"{header}\n=== ORIGINAL TASK ===\n{prompt[:8000]}\n\n"
                       f"=== CANDIDATES ===\n{cand_block}\n\n"
                       f"FINAL RESPONSE:")
    for prov, model in judge_pool:
        try:
            final, jlabel = _call_free(prov, model, critique_prompt, max_tokens)
            names = "+".join(lab.split(":")[0] for lab, _ in candidates)
            _log_council(len(candidates), names, jlabel, time.time() - t0)
            return final, 0.0, f"council:{names}->judge:{jlabel}"
        except Exception:
            traceback.print_exc()
            continue
    # Judge failed everywhere — best single candidate is still a valid free draft.
    lab, txt = candidates[0]
    return txt, 0.0, f"council:solo:{lab}"


def debate_or_chat(prompt: str, max_tokens: int = 1800):
    """Council when possible; existing paid llm.chat() only as last resort.
    Always returns (text, cost_usd, label)."""
    if enabled():
        try:
            return debate(prompt, max_tokens=max_tokens)
        except Exception:
            traceback.print_exc()
    from agent import llm as _llm
    return _llm.chat(prompt, max_tokens=max_tokens)


def free_or_chat(prompt: str, max_tokens: int = 800):
    """v5.8.3: ONE free-model call (no debate) with paid llm.chat() fallback.
    For low-stakes prompts: captions, replies, research lists, repurposing.
    Always returns (text, cost_usd, label) — drop-in for llm.chat()."""
    if enabled():
        try:
            text, label = free_chat(prompt, max_tokens=max_tokens)
            return text, 0.0, f"council:{label}"
        except Exception:
            traceback.print_exc()
    from agent import llm as _llm
    return _llm.chat(prompt, max_tokens=max_tokens)


def _log_council(n_cand: int, names: str, judge: str, secs: float):
    try:
        from . import ledger as _ldgr  # noqa
    except Exception:
        pass
    try:
        from agent import ledger as _legacy
        _legacy.record("council", model=f"{names}->%s" % judge, cost_usd=0.0,
                       detail=f"{n_cand} drafts merged in {secs:.1f}s")
    except Exception:
        pass
