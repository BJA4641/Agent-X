"""departments/paused_prep.py — v5.9.5 $0 prep for paused accounts.

Founder mandate (DEC-024): the ~100 paused accounts must cost exactly $0,
but sitting completely idle wastes the wait. This department lets them
compound *resume-ready* inventory using ONLY free models.

  paused.prep_cycle  (recurring, PAUSED_PREP_INTERVAL_S, default 3600s)
      Picks up to PREP_ACCOUNTS_PER_CYCLE paused accounts (least recently
      prepped first) and, for each one that has fewer than
      PREP_MAX_PER_ACCOUNT prep items banked, drafts ONE short script
      outline via council.free_chat and stores it as a board item with
      status='prep' (DEC-025: excluded from quota and in-flight math —
      _count_inflight and SLA _produced_today never see it).

HARD $0 GUARANTEE:
  * The ONLY model entry point in this file is council.free_chat, which by
    contract costs 0.0 and raises if no free provider is available.
  * If free providers are all down, the task silently skips — $0 beats
    progress for paused accounts.
  * A source-level test (test_v595_sla_governor.py) asserts no paid path
    is importable/reachable from _run_task. Do NOT add llm/council paid
    calls here — the test will fail the build.
"""
from __future__ import annotations
import os
import time
import datetime as _dt
from agentcore import Worker, Job, AgentContext, Priority
from ..common import board_add

PAUSED_PREP_INTERVAL_S = int(os.environ.get("PAUSED_PREP_INTERVAL_S", "3600"))
PREP_ACCOUNTS_PER_CYCLE = int(os.environ.get("PREP_ACCOUNTS_PER_CYCLE", "3"))
PREP_MAX_PER_ACCOUNT = int(os.environ.get("PREP_MAX_PER_ACCOUNT", "5"))


def register(w: Worker):
    w.register("paused.prep_cycle", prep_cycle)


def _prep_count(sb, account_id) -> int:
    try:
        res = (sb.table("board_items").select("id", count="exact")
               .eq("status", "prep").eq("account_id", str(account_id)).execute())
        return int(res.count or 0)
    except Exception:
        return PREP_MAX_PER_ACCOUNT  # unknown -> assume full, spend nothing


def _pick_paused(sb, limit: int) -> list:
    """Paused accounts, least-recently-prepped first (config.last_prep_at)."""
    try:
        rows = (sb.table("project_accounts").select("*")
                .eq("paused", True).limit(200).execute().data) or []
    except Exception:
        return []
    def key(a):
        cfg = a.get("config") or {}
        return float(cfg.get("last_prep_at") or 0)
    rows.sort(key=key)
    return rows[:limit]


def _run_task(sb, bus, job, acct) -> bool:
    """Draft ONE prep outline for one paused account. FREE MODELS ONLY —
    the single model call below is council.free_chat (cost 0.0 by contract).
    Returns True if an item was banked."""
    niche = acct.get("niche") or "general"
    handle = acct.get("handle") or "?"
    prompt = (
        f"You are prepping evergreen short-video content for a paused social "
        f"account in the '{niche}' niche (@{handle}). Write ONE reel outline: "
        f"a hook line (<=12 words), 4 numbered beats (one sentence each), and "
        f"a CTA line. Plain text only, no markdown, no preamble."
    )
    try:
        from agentcore.council import free_chat
        text, _cost, label = free_chat(prompt, max_tokens=400)
    except Exception:
        return False  # free providers down -> skip silently ($0 > progress)
    text = (text or "").strip()
    if not text:
        return False
    hook = text.splitlines()[0][:120] if text.splitlines() else f"{niche} prep"
    try:
        board_add(sb, f"[prep] {hook}",
                  {"bucket": "prep", "outline": text[:4000],
                   "prepared_at": _dt.datetime.utcnow().isoformat() + "Z",
                   "model": label, "niche": niche},
                  status="prep", account_id=acct["id"])
    except Exception:
        return False
    bus.agent("planner", f"📦 prep banked for paused @{handle} — \"{hook[:60]}\" ($0, {label})",
              "info", "prep_banked", job_id=job.id, account_id=acct["id"])
    return True


def prep_cycle(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    banked = 0
    if sb is not None:
        for acct in _pick_paused(sb, PREP_ACCOUNTS_PER_CYCLE):
            if _prep_count(sb, acct["id"]) >= PREP_MAX_PER_ACCOUNT:
                continue
            if _run_task(sb, bus, job, acct):
                banked += 1
            # stamp last_prep_at so rotation is fair even on skip
            try:
                cfg = dict(acct.get("config") or {})
                cfg["last_prep_at"] = time.time()
                sb.table("project_accounts").update({"config": cfg}) \
                  .eq("id", str(acct["id"])).execute()
            except Exception:
                pass
    # self-schedule next cycle (idempotent per interval bucket)
    nxt = time.time() + PAUSED_PREP_INTERVAL_S
    j = Job(job_type="paused.prep_cycle", payload={}, priority=Priority.LOW,
            scheduled_for=nxt,
            idempotency_key=f"prep:{int(nxt // PAUSED_PREP_INTERVAL_S)}")
    w.queue.enqueue(j)
    w.queue.complete(job, {"ok": True, "banked": banked})
