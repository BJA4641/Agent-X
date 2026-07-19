"""workers/common.py — helpers shared by every v2 worker/agent.

Every agent handler here is a thin wrapper that:
  1. Pulls deps from ctx.deps (bus, queue, supabase, tracer).
  2. Loads whatever state it needs from the job payload / DB.
  3. Delegates to the existing (v4.3) functions in `agent.*` for the
     heavy lifting (scripting, rendering, etc.) so we don't throw away
     what already works.
  4. Emits events onto the bus, records cost, and spawns follow-up jobs.

This "wrapper/strangler" pattern means Phase 2 migrates the CONTROL PLANE
(event bus + job queue + departmental org chart) without rewriting every
creative module in one go — the working LLM/render code stays in `agent/`.
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
    """Chain a follow-up job at the same priority as the parent."""
    return job_of(worker, job_type, payload, parent=parent,
                  priority=parent.priority, **kw)


# --------------------------------------------------------------------- board_items bridge

def board_add(sb, topic: str, payload: dict, status: str = "idea") -> dict:
    """Insert a board_item (legacy content board). Returns the row."""
    row = {"topic": topic[:200], "payload": payload or {}, "status": status}
    res = sb.table("board_items").insert(row).execute()
    return (res.data or [row])[0]


def board_get(sb, item_id: str) -> Optional[dict]:
    try:
        res = sb.table("board_items").select("*").eq("id", str(item_id)).single().execute()
        return res.data
    except Exception:
        return None


def board_patch(sb, item_id: str, **patch) -> Optional[dict]:
    try:
        res = sb.table("board_items").update(patch).eq("id", str(item_id)).execute()
        return (res.data or [None])[0]
    except Exception:
        return None


def board_patch_payload(sb, item_id: str, patch: dict) -> Optional[dict]:
    """Merge patch into payload jsonb. Non-destructive."""
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
    Cached briefly to reduce chattiness."""
    now = time.time()
    if now - _ACTIVE_ACCOUNT_CACHE["at"] < ttl_s and _ACTIVE_ACCOUNT_CACHE["rows"]:
        return _ACTIVE_ACCOUNT_CACHE["rows"]
    rows = []
    if sb is None:
        _ACTIVE_ACCOUNT_CACHE.update(at=now, rows=[])
        return []
    try:
        res = (sb.table("project_accounts")
               .select("id,name,handle,niche,project_id,platforms,status,"
                       "daily_budget_usd,posts_per_day,brand_bible,paused")
               .eq("paused", False).execute())
        projects_to_check = {}
        for a in res.data or []:
            pid = a.get("project_id")
            if pid:
                projects_to_check.setdefault(pid, []).append(a)
            else:
                rows.append(a)
        # Filter by parent project paused
        for pid, accts in projects_to_check.items():
            try:
                pj = sb.table("projects").select("paused,name").eq("id", pid).single().execute().data
                if pj and not pj.get("paused"):
                    for a in accts:
                        a["project_name"] = pj.get("name")
                        rows.append(a)
            except Exception:
                continue
    except Exception as e:
        traceback.print_exc()
    _ACTIVE_ACCOUNT_CACHE.update(at=now, rows=rows)
    return rows


def first_active_account(sb) -> Optional[dict]:
    """The user mandated: start with ONE active account, user manually resumes others."""
    accts = active_accounts(sb)
    return accts[0] if accts else None


def load_account(sb, account_id) -> Optional[dict]:
    if sb is None or not account_id:
        return None
    try:
        a = (sb.table("project_accounts").select("*")
             .eq("id", str(account_id)).single().execute().data)
        return a
    except Exception:
        return None


def brand_context_for(sb, account_id: str) -> dict:
    """Load the Brand Bible + playbook docs for the account. Returns dict with
    empty strings as safe defaults (old templates degrade gracefully)."""
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
        # Backwards compat aliases
        if not out["business_plan"]:    out["business_plan"]    = out["executive_summary"]
        if not out["brand_guidelines"]: out["brand_guidelines"] = out["brand_identity"]
        if not out["tone_guide"]:       out["tone_guide"]       = out["brand_identity"]
        if not out["visual_rules"]:     out["visual_rules"]     = out["visual_identity"]
        return out
    except Exception:
        return empty


# --------------------------------------------------------------------- budget / kill switch

def hard_budget_ok() -> bool:
    """Global daily-budget gate, checked at the top of every content workflow."""
    from agentcore import ledger as _l, config as _cfg
    return _l.budget_ok(next_cost_usd=0.01, daily_budget=_cfg.DAILY_BUDGET_USD)


def kill_switch() -> bool:
    from agentcore import config as _cfg
    return _cfg.kill_switch_on()


# --------------------------------------------------------------------- tiny agent bases

class _LoggedAgent(BaseAgent):
    """Helper base that logs entry/exit on the bus."""
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
