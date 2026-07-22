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
    ("groq",       "llama-3.3-70b-versatile"),
    ("openrouter", "moonshotai/kimi-k2:free"),
    ("gemini",     "gemini-2.5-flash"),
]

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
    """Free providers whose API keys are actually configured."""
    from agent import llm as _llm
    return [(p, m) for (p, m) in _FREE_ORDER if _llm._has_key(p)]


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
    Returns (text, 0.0, label). Raises RuntimeError if no free provider works."""
    last = None
    for prov, model in _providers():
        try:
            text, label = _call_free(prov, model, prompt, max_tokens)
            return text, 0.0, f"free:{label}"
        except Exception as e:
            last = e
            continue
    raise RuntimeError(f"no free provider available: {last}")


def debate(prompt: str, max_tokens: int = 1800):
    """Full council: 2 free drafts → free critique/merge → final text.
    Degrades gracefully: 1 provider → draft + self-critique pass.
    Returns (text, 0.0, label)."""
    provs = _providers()
    if not provs:
        raise RuntimeError("council: no free providers configured")

    t0 = time.time()
    candidates = []           # [(label, text)]
    for prov, model in provs[:2]:
        try:
            text, label = _call_free(prov, model, prompt, max_tokens)
            candidates.append((label, text))
        except Exception:
            traceback.print_exc()
            continue
    if not candidates:
        raise RuntimeError("council: all free drafts failed")

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
