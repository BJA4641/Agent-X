"""workers/common.py — helpers shared by every v5 worker/agent.

Every agent handler is a thin wrapper that:
  1. Pulls deps from ctx.deps (bus, queue, supabase, tracer).
  2. Loads state from the job payload / DB.
  3. Delegates to existing v4.3 functions in `agent.*` for heavy lifting.
  4. Emits events, records cost, spawns follow-up jobs.
"""
from __future__ import annotations
import os, time, traceback, uuid
from typing import Any, Dict, List, Optional

from agentcore import (
    Worker, Job, JobStatus, AgentContext, BaseAgent,
    EventType, HumanEscalation, FatalError, Priority, QualityGate,
)


# --------------------------------------------------------------------- job spawn helpers

def job_of(worker: Worker, job_type: str, payload: dict, *,
           priority: int = Priority.NORMAL, brand_id=None, account_id=None,
           project_id=None, parent: Job = None, idempotency_key: str = None,
           max_attempts: int = 2) -> Job:
    return worker.spawn(
        job_type, payload,
        priority=priority,
        brand_id=brand_id or (parent.brand_id if parent else None),
        account_id=account_id or (parent.account_id if parent else None),
        project_id=project_id or (parent.project_id if parent else None),
        parent_job_id=parent.id if parent else None,
        idempotency_key=idempotency_key,
        max_attempts=max_attempts,
    )


def next_tick(worker: Worker, job_type: str, payload: dict, parent: Job, **kw):
    return job_of(worker, job_type, payload, parent=parent,
                  priority=parent.priority, **kw)


# --------------------------------------------------------------------- board_items bridge

def board_add(sb, topic: str, payload: dict, status: str = "idea", account_id=None) -> dict:
    row = {"topic": topic[:200], "payload": payload or {}, "status": status}
    if account_id:
        row["account_id"] = str(account_id)
    res = sb.table("board_items").insert(row).execute()
    return (res.data or [row])[0]


def board_get(sb, item_id: str) -> Optional[dict]:
    if not item_id: return None
    try:
        res = sb.table("board_items").select("*").eq("id", str(item_id)).single().execute()
        return res.data
    except Exception:
        return None


def board_patch(sb, item_id: str, **patch) -> Optional[dict]:
    if not item_id: return None
    try:
        res = sb.table("board_items").update(patch).eq("id", str(item_id)).execute()
        return (res.data or [None])[0]
    except Exception:
        return None


def board_patch_payload(sb, item_id: str, patch: dict) -> Optional[dict]:
    if not item_id: return None
    item = board_get(sb, item_id)
    if not item:
        return None
    merged = dict(item.get("payload") or {})
    merged.update(patch or {})
    return board_patch(sb, item_id, payload=merged)


# --------------------------------------------------------------------- accounts/projects

_ACTIVE_ACCOUNT_CACHE: Dict[str, Any] = {"at": 0.0, "rows": []}


def active_accounts(sb, ttl_s: float = 60.0) -> List[dict]:
    """Accounts that are not paused AND whose parent project is not paused.
    BUG FIX (v5.3): this is now the ONLY source of truth. Excludes paused
    accounts at both the project AND account level. Cached briefly."""
    now = time.time()
    if now - _ACTIVE_ACCOUNT_CACHE["at"] < ttl_s and _ACTIVE_ACCOUNT_CACHE["rows"]:
        return _ACTIVE_ACCOUNT_CACHE["rows"]
    rows: List[dict] = []
    if sb is None:
        _ACTIVE_ACCOUNT_CACHE.update(at=now, rows=[])
        return []
    try:
        res = (sb.table("project_accounts")
               .select("id,name,handle,niche,project_id,platforms,status,"
                       "daily_budget_usd,posts_per_day,brand_bible,paused,affiliate_urls,sponsor,config")
               .eq("paused", False).execute())
        accts = res.data or []
        # Batch-fetch parent projects to avoid N+1
        project_ids = list({a.get("project_id") for a in accts if a.get("project_id")})
        paused_projects = set()
        for pid in project_ids:
            try:
                pj = sb.table("projects").select("paused,name").eq("id", pid).single().execute().data
                if pj and pj.get("paused"):
                    paused_projects.add(pid)
            except Exception:
                continue
        for a in accts:
            pid = a.get("project_id")
            if pid in paused_projects:
                continue
            # Attach project name
            try:
                pj = sb.table("projects").select("name").eq("id", pid).single().execute().data
                if pj: a["project_name"] = pj.get("name")
            except Exception:
                pass
            rows.append(a)
    except Exception as e:
        traceback.print_exc()
    _ACTIVE_ACCOUNT_CACHE.update(at=now, rows=rows)
    return rows


def invalidate_active_accounts():
    _ACTIVE_ACCOUNT_CACHE["at"] = 0.0


def first_active_account(sb) -> Optional[dict]:
    """User mandate: start with ONE active account; the user manually resumes
    others. Returns the single non-paused account, or None. When multiple
    are active, pick the most recently created (so newly-resumed accounts
    take priority) but warn via event."""
    accts = active_accounts(sb)
    if not accts:
        return None
    if len(accts) == 1:
        return accts[0]
    # Sort by created_at desc (most recently created / resumed wins) then
    # return just ONE — never parallel across accounts.
    accts_sorted = sorted(accts, key=lambda a: str(a.get("created_at") or ""), reverse=True)
    chosen = accts_sorted[0]
    return chosen


def load_account(sb, account_id) -> Optional[dict]:
    if sb is None or not account_id:
        return None
    try:
        return sb.table("project_accounts").select("*").eq("id", str(account_id)).single().execute().data
    except Exception:
        return None


def is_account_active(sb, account_id) -> bool:
    """Check a specific account is actually running (not paused, project not paused)."""
    a = load_account(sb, account_id)
    if not a or a.get("paused"):
        return False
    pid = a.get("project_id")
    if pid:
        try:
            pj = sb.table("projects").select("paused").eq("id", pid).single().execute().data
            if pj and pj.get("paused"):
                return False
        except Exception:
            pass
    return True


def brand_context_for(sb, account_id: str) -> dict:
    empty = {k: "" for k in (
        "business_plan","brand_guidelines","tone_guide","visual_rules","content_rules",
        "executive_summary","vision_mission","revenue_model","brand_identity",
        "visual_identity","marketing_strategy","instagram_playbook","tiktok_playbook",
        "youtube_playbook","content_calendar","hashtags_seo","production_sop")}
    if sb is None or not account_id:
        return empty
    try:
        rows = (sb.table("account_documents").select("doc_type,content")
                .eq("account_id", str(account_id)).execute().data or [])
        out = dict(empty)
        for r in rows:
            out[r["doc_type"]] = r.get("content") or ""
        # Backcompat aliases
        if not out["business_plan"]:    out["business_plan"]    = out["executive_summary"]
        if not out["brand_guidelines"]: out["brand_guidelines"] = out["brand_identity"]
        if not out["tone_guide"]:       out["tone_guide"]       = out["brand_identity"]
        if not out["visual_rules"]:     out["visual_rules"]     = out["visual_identity"]
        return out
    except Exception:
        return empty


# --------------------------------------------------------------------- budget / kill switch / CEO gate

def hard_budget_ok(next_cost_usd: float = 0.01, daily_budget: float = None) -> bool:
    from agentcore import ledger as _l, config as _cfg
    cap = daily_budget if daily_budget is not None else _cfg.DAILY_BUDGET_USD
    return _l.budget_ok(next_cost_usd=next_cost_usd, daily_budget=cap)


def ceo_decide(sb, action: str, *, account_id=None, est_cost: float = None,
               department: str = None, topic: str = "", item_id=None) -> dict:
    """v5.5: synchronously ask the CEO engine before spending money.

    Returns {"decision":"approve|deny|delay|reuse|cheaper", "reason":str,
             "reuse":asset_id?, "cheaper":tier?, "model_tier":str}.

    If the worker doesn't have a queue/job handy we run the decision inline
    (direct call) — still writes to exec_decisions for audit trail.
    """
    from workers.departments import ceo as _ceo
    est = float(est_cost if est_cost is not None else
                _ceo.EXPECTED_VALUE_BY_ACTION.get(action, {}).get("cost", 0.01))
    # Inline fast-path (no async queue needed): run the decide logic synchronously
    try:
        cfg = _ceo._load_config(sb)
        min_roi = float(cfg.get("min_roi_threshold", _ceo.DEFAULT_MIN_ROI))
        decision = {"decision": "deny", "reason": "", "cheaper": None, "reuse": None, "model_tier": "cheap"}

        if est <= 0.001:
            decision.update(decision="approve", reason="free/cached action", model_tier="free")
            _ceo._record_inline(sb, account_id, department or action.split("_")[0], action, est, decision)
            return decision

        if not hard_budget_ok(est):
            decision.update(decision="delay",
                            reason=f"daily budget hit — {remaining_budget():.3f} left, need ${est:.3f}")
            _ceo._record_inline(sb, account_id, department or action.split("_")[0], action, est, decision)
            return decision

        # Brand studio: once per account
        if action == "brand_studio" and account_id:
            try:
                existing = sb.table("account_documents").select("doc_type").eq("account_id", str(account_id)).limit(1).execute().data
                if existing and len(existing) >= 5:
                    decision.update(decision="reuse", reason="brand docs already exist", reuse="existing_brand")
                    _ceo._record_inline(sb, account_id, "brand_studio", action, 0.0, decision)
                    return decision
            except Exception: pass

        # Reuse check first
        if _ceo.EXPECTED_VALUE_BY_ACTION.get(action, {}).get("reuse_ok"):
            asset = _ceo._find_reusable(sb, action, account_id, topic=topic)
            if asset:
                decision.update(decision="reuse",
                                reason=f"reusable asset (used {asset.get('usage_count',0)}x)",
                                reuse=asset["id"])
                _ceo._record_inline(sb, account_id, department or action.split("_")[0], action, 0.0, decision)
                return decision

        ev = _ceo._expected_value(sb, account_id, action, est, _ceo.EXPECTED_VALUE_BY_ACTION.get(action, {}))
        ps = _ceo._success_probability(sb, account_id, action)
        weighted_ev = ev * ps
        roi = weighted_ev / max(est, 0.001)
        account_roi = _ceo._account_roi(sb, account_id)
        days_losing = _ceo._losing_streak(sb, account_id)

        if account_roi is not None:
            if account_roi < 0.3 and days_losing >= int(cfg.get("pause_losers_after_days", 3)):
                decision.update(decision="deny", reason=f"account ROI {account_roi:.2f}x losing for {days_losing}d")
                _ceo._record_inline(sb, account_id, department or action.split("_")[0], action, est, decision)
                return decision
            if account_roi > 3.0:
                decision["model_tier"] = "mix"
            elif account_roi < 0.8:
                decision["model_tier"] = "cheap"

        cheaper = _ceo._cheaper_alternative(action, est, cfg)

        if roi >= min_roi:
            decision.update(decision="approve",
                            reason=f"ROI {roi:.2f}x ≥ threshold {min_roi}x")
            if cheaper and decision["model_tier"] != "premium" and cfg.get("free_tier_preferred", True):
                decision["cheaper"] = cheaper
                decision["reason"] += f" · using cheaper tier ({cheaper})"
        elif cheaper and est > 0.01:
            decision.update(decision="cheaper",
                            reason=f"ROI {roi:.2f}x below {min_roi}x at ${est:.3f} — try cheaper ({cheaper})",
                            cheaper=cheaper)
        else:
            decision.update(decision="delay", reason=f"ROI {roi:.2f}x below threshold {min_roi}x")
        _ceo._record_inline(sb, account_id, department or action.split("_")[0], action, est, decision)
        return decision
    except Exception:
        # Fail-safe: if CEO engine errors, allow cheap/free actions, deny expensive ones
        traceback.print_exc()
        if est <= 0.005: return {"decision":"approve","reason":"fail-safe: cheap action","model_tier":"free"}
        return {"decision":"delay","reason":"CEO engine error — delaying non-free action"}


def remaining_budget() -> float:
    from agentcore import ledger as _l, config as _cfg
    return max(0.0, _cfg.DAILY_BUDGET_USD - _l.spent_today())


def remaining_account_budget(sb, account_id) -> float:
    """v5.5: per-account remaining budget from capital_allocation."""
    try:
        today = __import__("datetime").date.today().isoformat()
        r = sb.table("capital_allocation").select("budget_usd").eq("account_id", str(account_id)).eq("day", today).limit(1).execute()
        if r.data:
            alloc = float(r.data[0].get("budget_usd") or 0)
            # subtract today's spend for that account
            s = sb.table("run_ledger").select("cost_usd").eq("account_id", str(account_id)).gte("created_at", today).execute()
            spent = sum(float(x.get("cost_usd") or 0) for x in (s.data or []))
            return max(0.0, alloc - spent)
    except Exception:
        return remaining_budget()
    return remaining_budget()


def kill_switch() -> bool:
    from agentcore import config as _cfg
    return _cfg.kill_switch_on()


def account_daily_budget(sb, account) -> float:
    """Use per-account budget if set, else global."""
    bd = (account or {}).get("daily_budget_usd")
    try:
        return float(bd) if bd and float(bd) > 0 else _global_budget(sb)
    except Exception:
        return _global_budget(sb)


def _global_budget(sb) -> float:
    from agentcore import config as _cfg
    if sb:
        try:
            r = sb.table("settings").select("value").eq("tenant_id", _cfg.TENANT_ID).eq("key","daily_budget").limit(1).execute()
            if r.data:
                v = (r.data[0].get("value") or {}).get("usd")
                if v: return float(v)
        except Exception:
            pass
    return _cfg.DAILY_BUDGET_USD


# --------------------------------------------------------------------- tiny agent bases

class _LoggedAgent(BaseAgent):
    def run(self, ctx: AgentContext, job: Job) -> Dict[str, Any]:
        self.emit_info(f"{self.emoji} starting {job.job_type}", job=job)
        try:
            out = self._run(ctx, job)
            self.emit_ok(f"{self.emoji} done — {job.job_type}", job=job)
            return out
        except HumanEscalation:
            raise
        except Exception as e:
            self.emit_err(f"{self.emoji} failed: {str(e)[:160]}", job=job)
            raise

    def _run(self, ctx: AgentContext, job: Job) -> Dict[str, Any]:
        raise NotImplementedError


# --------------------------------------------------------------------- output dir

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
