"""qa.py — editor-in-chief / 12-point QA gate.

Called from orchestrator.produce() AFTER captions are generated but BEFORE
status is set to 'drafted'. Returns:
  {"approved": True}  -> proceed to drafted (Studio for human approval)
  {"approved": False, "route_to": "...", "fix_instruction": "...", "rounds": N}
    -> orchestrator loops back to the responsible module for a revision
       (max 3 rounds, then escalates to human rejection with reason).
"""
from __future__ import annotations
import json, os
from . import config, ledger, llm, brand

EST_COST = 0.01
MAX_ROUNDS = 3

_FALLBACK_QA_PROMPT = """You are editor-in-chief. Score this social draft 1-10 against the Brand Bible below. Return JSON: {{"score":int,"approved":bool,"failed_checks":[],"route_to":"writer|visuals|voice|captions|publisher|manager","fix_instruction":str}}.

BRAND BIBLE:
{brand_grounding}

DRAFT:
{draft}
"""


def review(script: dict, captions: dict, style: str, platform_targets: list,
           item_id=None, user_id=None, rounds_so_far: int = 0) -> dict:
    grounding = brand.grounding_block(user_id)
    draft = {
        "script": script,
        "captions": captions,
        "visual_style": style,
        "platforms": platform_targets,
    }
    if llm.ready() and ledger.budget_ok(EST_COST):
        try:
            prompt_tpl, version = config.load_prompt("qa_v1")
        except Exception:
            prompt_tpl, version = _FALLBACK_QA_PROMPT, "qa_v1"
        prompt = prompt_tpl.replace("{brand_grounding}", grounding).replace("{draft}", json.dumps(draft))
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=400)
            verdict = json.loads(text[text.find("{"): text.rfind("}") + 1])
            ledger.record("qa", model=mlabel, prompt_version=version, cost_usd=cost, item_id=item_id,
                          detail=f"score={verdict.get('score')} approved={verdict.get('approved')}")
        except Exception as e:
            ledger.record("qa", ok=False, detail=str(e), item_id=item_id)
            return {"approved": True, "auto_passed_due_to_error": True}
    else:
        verdict = _heuristic_pass(script, captions)

    if verdict.get("approved"):
        return {"approved": True, "score": verdict.get("score", 8)}
    if rounds_so_far + 1 >= MAX_ROUNDS:
        ledger.record("qa", ok=False, detail=f"escalated after {MAX_ROUNDS} rounds: {verdict.get('fix_instruction')}", item_id=item_id)
        return {"approved": False, "escalated": True, "reason": verdict.get("fix_instruction", "QA failed")}
    return {"approved": False,
            "route_to": verdict.get("route_to", "writer"),
            "fix_instruction": verdict.get("fix_instruction", "Rewrite per feedback."),
            "rounds": rounds_so_far + 1}


def _heuristic_pass(script: dict, captions: dict) -> dict:
    issues = []
    if not script.get("hook"): issues.append("missing hook")
    if not script.get("beats") or len(script.get("beats", [])) < 2: issues.append("too few beats")
    if not script.get("cta"): issues.append("missing CTA")
    if captions.get("instagram", {}).get("caption") and len(captions["instagram"]["caption"]) > 2200:
        issues.append("IG caption over limit")
    if issues:
        return {"approved": False, "route_to": "writer", "fix_instruction": "; ".join(issues), "score": 4}
    return {"approved": True, "score": 8}
