"""departments/ceo.py — v5.5 Autonomous CEO Engine.

Primary objective (per the CEO directive):
  MAXIMIZE long-term profit, ROI, brand value; MINIMIZE unnecessary spend.
  Never optimize for # of posts.

Every spending decision routes through decide() BEFORE any money is spent.
The CEO writes a row to exec_decisions with approve/deny/delay/reuse/cheaper
and a reason. Nothing runs without an approve decision.

Daily CEO tick (run once per day, and on-demand):
  1. Compute ROI per account from roi_snapshots (views, followers, revenue, spend).
  2. Allocate daily budgets — scale winners, pause losers, recycle unused $.
  3. Search asset_library for reusable content (promote reuse over generation).
  4. Write 3-7 ceo_recommendations for the human CEO (you).
"""
from __future__ import annotations
import datetime, hashlib, json, math, os, time, traceback
from typing import Optional, Dict, Any, List

from agentcore import Worker, Job, AgentContext, Priority
from ..common import job_of, hard_budget_ok, remaining_budget, account_daily_budget

# Departments: how much we EXPECT each action to earn back on a new account
# (mature accounts with revenue history override these with their real ROI.)
# Multiples = expected $ revenue per $1 spent at cold start.
EXPECTED_VALUE_BY_ACTION = {
    # Low-cost, discovery phase
    "scout":            {"cost": 0.00, "ev": 0.05, "reuse_ok": True},   # free (Reddit/HN)
    "ideate":           {"cost": 0.02, "ev": 0.06, "reuse_ok": True},   # topic selection
    "write_script":     {"cost": 0.04, "ev": 0.20, "reuse_ok": True},   # script = asset
    "grade_script":     {"cost": 0.005, "ev": 0.08, "reuse_ok": False},  # quality gate
    "render_image":     {"cost": 0.02, "ev": 0.10, "reuse_ok": True},
    "tts":              {"cost": 0.005, "ev": 0.03, "reuse_ok": True},
    "render_video":     {"cost": 0.15, "ev": 0.40, "reuse_ok": True},   # AI video = expensive
    "edit_video":       {"cost": 0.05, "ev": 0.15, "reuse_ok": False},
    "caption_burn":     {"cost": 0.00, "ev": 0.10, "reuse_ok": False},  # local ffmpeg, free
    "distribute":       {"cost": 0.00, "ev": 0.30, "reuse_ok": False},  # API calls
    "reply_comments":   {"cost": 0.005, "ev": 0.05, "reuse_ok": False},
    "brand_studio":     {"cost": 0.00, "ev": 0.20, "reuse_ok": True},   # one-time per account
    "analyze":          {"cost": 0.00, "ev": 0.02, "reuse_ok": False},
}

# Minimum ROI multiple required to approve spend (set by settings.ceo_config.min_roi_threshold)
DEFAULT_MIN_ROI = 1.5


def register(w: Worker):
    w.register("ceo.decide",           ceo_decide)
    w.register("ceo.daily_tick",       ceo_daily_tick)
    w.register("ceo.allocate_budgets", ceo_allocate_budgets)
    w.register("ceo.reuse_search",     ceo_reuse_search)
    w.register("ceo.record_outcome",   ceo_record_outcome)


# ---------------------------------------------------------------- DECIDE
def ceo_decide(w: Worker, job: Job, ctx: AgentContext):
    """Approve / deny / delay / reuse a spending request.

    Expected job.payload:
      { action, department, account_id, estimated_cost_usd, item_id?, context? }
    Returns (writes job.result with decision + reason).
    """
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()  # v5.8.2 FIX: Worker has no .sb
    bus = ctx.deps["bus"]
    p = job.payload or {}
    action     = p.get("action", "unknown")
    dept       = p.get("department", job.job_type.split(".")[0])
    account_id = p.get("account_id")
    est_cost   = float(p.get("estimated_cost_usd") or EXPECTED_VALUE_BY_ACTION.get(action, {}).get("cost", 0.01))
    force      = bool(p.get("force", False))

    decision = {"decision": "deny", "reason": "", "cheaper": None, "reuse": None, "model_tier": "cheap"}

    # Load CEO config
    cfg = _load_config(sb)
    min_roi = float(cfg.get("min_roi_threshold", DEFAULT_MIN_ROI))

    # Emergency brakes first (these override everything)
    if not force and not hard_budget_ok(next_cost_usd=est_cost):
        decision.update(decision="delay", reason=f"daily budget hit — {remaining_budget():.3f} left, need ${est_cost:.3f}. Reschedule after midnight.")
        return _record(sb, w, job, account_id, dept, action, est_cost, decision)

    # Free actions (scout, caption_burn, distribute, analyze, brand_studio first run) always go through
    if est_cost <= 0.001:
        decision.update(decision="approve", reason="free/cached action", model_tier="free")
        return _record(sb, w, job, account_id, dept, action, est_cost, decision)

    # Brand studio runs once per account — check if already done, but it's zero cost.
    if action == "brand_studio":
        existing = sb.table("account_documents").select("doc_type").eq("account_id", str(account_id)).limit(1).execute().data if account_id else []
        if existing and len(existing) >= 5:
            decision.update(decision="reuse", reason=f"brand docs already exist ({len(existing)} docs)", reuse="existing_brand")
        else:
            decision.update(decision="approve", reason="first-time brand doc generation", model_tier="cheap")
        return _record(sb, w, job, account_id, dept, action, est_cost, decision)

    # --- Check asset library for reusable content FIRST (reuse before generate)
    if EXPECTED_VALUE_BY_ACTION.get(action, {}).get("reuse_ok"):
        reuse_asset = _find_reusable(sb, action, account_id, topic=p.get("topic", ""))
        if reuse_asset:
            decision.update(
                decision="reuse",
                reason=f"reusable asset found (used {reuse_asset.get('usage_count',0)}x, score {reuse_asset.get('performance_score','?')}). $0 incremental cost.",
                reuse=reuse_asset["id"],
            )
            return _record(sb, w, job, account_id, dept, action, 0.0, decision)

    # --- Compute expected value
    ev = _expected_value(sb, account_id, action, est_cost, default_cfg=EXPECTED_VALUE_BY_ACTION.get(action, {}))
    p_success = _success_probability(sb, account_id, action)
    weighted_ev = ev * p_success
    roi = weighted_ev / max(est_cost, 0.001)

    # --- Check for cheaper model tier
    cheaper = _cheaper_alternative(action, est_cost, cfg)

    # --- Account ROI history
    account_roi = _account_roi(sb, account_id)
    days_losing = _losing_streak(sb, account_id)

    # --- Decision logic
    if account_roi is not None:
        # Mature account: trust its track record
        if account_roi < 0.3 and days_losing >= int(cfg.get("pause_losers_after_days", 3)):
            decision.update(decision="deny", reason=f"account ROI {account_roi:.2f}x < 1x for {days_losing} days — pause until human review or trend changes")
            return _record(sb, w, job, account_id, dept, action, est_cost, decision)
        if account_roi > 3.0:
            # Scale winners: approve premium tier
            decision.update(model_tier="mix")
        if account_roi < 0.8:
            # Weak performance — downgrade to cheap/free only
            decision.update(model_tier="cheap")

    if roi >= min_roi:
        decision.update(
            decision="approve",
            reason=f"expected ROI {roi:.2f}x (EV ${weighted_ev:.3f}, P={p_success:.2f}) ≥ threshold {min_roi}x",
        )
        if cheaper and decision["model_tier"] != "premium" and cfg.get("free_tier_preferred", True):
            decision["cheaper"] = cheaper
            decision["reason"] += f". Using cheaper tier ({cheaper})"
    elif cheaper and est_cost > 0.01:
        decision.update(
            decision="cheaper",
            reason=f"ROI {roi:.2f}x below threshold ${min_roi}x at ${est_cost:.3f} — retrying with cheaper model ({cheaper})",
            cheaper=cheaper,
        )
    elif ev <= 0:
        decision.update(decision="deny", reason=f"no expected value for action {action}")
    else:
        decision.update(
            decision="delay",
            reason=f"ROI {roi:.2f}x below threshold {min_roi}x (EV ${weighted_ev:.3f}). Try again tomorrow when budget resets or content is proven.",
        )

    return _record(sb, w, job, account_id, dept, action, est_cost, decision)


def _record_inline(sb, account_id, dept, action, est_cost, decision):
    """Inline version (no w/job) for the ceo_decide() fast-path used in common.py."""
    try:
        sb.table("exec_decisions").insert({
            "tenant_id": "me", "account_id": str(account_id) if account_id else None,
            "department": dept, "action": action, "estimated_cost_usd": est_cost,
            "expected_value_usd": decision.get("ev"),
            "expected_roi": decision.get("roi"),
            "success_probability": decision.get("p_success"),
            "decision": decision["decision"], "reason": decision.get("reason",""),
            "cheaper_alternative": decision.get("cheaper"),
            "reuse_asset_id": decision.get("reuse"),
            "model_selected": decision.get("model_tier","cheap"),
        }).execute()
    except Exception:
        traceback.print_exc()


def _record(sb, w, job, account_id, dept, action, est_cost, decision):
    """Persist the decision to exec_decisions and complete the job."""
    try:
        sb.table("exec_decisions").insert({
            "tenant_id": "me",
            "account_id": str(account_id) if account_id else None,
            "job_id": job.id,
            "department": dept,
            "action": action,
            "estimated_cost_usd": est_cost,
            "expected_value_usd": decision.get("ev"),
            "expected_roi": decision.get("roi"),
            "success_probability": decision.get("p_success"),
            "decision": decision["decision"],
            "reason": decision.get("reason",""),
            "cheaper_alternative": decision.get("cheaper"),
            "reuse_asset_id": decision.get("reuse"),
            "model_selected": decision.get("model_tier","cheap"),
        }).execute()
    except Exception as e:
        traceback.print_exc()
    w.queue.complete(job, {"ok": True, "decision": decision})


# ---------------------------------------------------------------- DAILY TICK
def ceo_daily_tick(w: Worker, job: Job, ctx: AgentContext):
    """Run once/day: compute ROI, allocate budgets, write recommendations."""
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()  # v5.8.2 FIX: Worker has no .sb
    bus = ctx.deps["bus"]
    bus.agent("ceo", "👔 starting daily CEO review", "info", "ceo_day_start", job_id=job.id)
    try:
        _snapshot_roi(sb)
        _allocate_budgets(sb, bus)
        recs = _write_recommendations(sb)
        bus.agent("ceo", f"👔 CEO review done — {recs} recommendations posted", "success", "ceo_day_done", job_id=job.id)
    except Exception as e:
        bus.agent("ceo", f"👔 CEO review error: {str(e)[:160]}", "error", "ceo_day_err", job_id=job.id)
    w.queue.complete(job, {"ok": True})


def ceo_allocate_budgets(w: Worker, job: Job, ctx: AgentContext):
    _sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()  # v5.8.2 FIX
    _allocate_budgets(_sb, ctx.deps["bus"])
    w.queue.complete(job, {"ok": True})


def ceo_reuse_search(w: Worker, job: Job, ctx: AgentContext):
    p = job.payload or {}
    _sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()  # v5.8.2 FIX
    asset = _find_reusable(_sb, p.get("action",""), p.get("account_id"), topic=p.get("topic",""))
    w.queue.complete(job, {"ok": True, "asset": asset})


def ceo_record_outcome(w: Worker, job: Job, ctx: AgentContext):
    """After an action finishes, update the asset_library (if reusable) and record ROI."""
    p = job.payload or {}
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()  # v5.8.2 FIX
    bus = ctx.deps["bus"]
    try:
        if p.get("store_asset") and p.get("asset_type"):
            # Media assets (video_path/image_path/voice_path) carry a blob_path; content is a path str
            asset_type = p["asset_type"]
            content = p.get("content") or ""
            blob_path = p.get("blob_path")
            perf = p.get("performance_score")
            if asset_type in ("video_path","image_path","voice_path") and not blob_path:
                blob_path = content  # path string itself is the blob reference
                content = ""  # don't bloat content column with filesystem path
            if content or blob_path:
                _store_asset(sb, asset_type, content, account_id=p.get("account_id"),
                             niche=p.get("niche"), cost=p.get("cost_usd",0),
                             tags=p.get("tags",[]), perf_score=perf, blob_path=blob_path)
                bus.agent("ceo", f"♻️ stored reusable {asset_type} asset", "info",
                          "asset_stored", job_id=job.id, item_id=p.get("item_id"))
        # Optional revenue_event record (e.g. affiliate click pixel firing)
        if p.get("revenue_usd") and p.get("revenue_source"):
            _record_revenue(sb, p.get("account_id"), p.get("item_id"),
                            float(p["revenue_usd"]), p["revenue_source"],
                            p.get("metadata") or {})
    except Exception:
        traceback.print_exc()
    w.queue.complete(job, {"ok": True})


# ============================================================ HELPERS

def _load_config(sb) -> dict:
    try:
        r = sb.table("settings").select("value").eq("tenant_id","me").eq("key","ceo_config").limit(1).execute()
        if r.data: return r.data[0]["value"] or {}
    except Exception:
        return {}
    return {}


def _find_reusable(sb, action: str, account_id, topic: str = "") -> Optional[dict]:
    """Search asset_library for a reusable asset of the matching type/niche.
    v5.5 P0: also considers blob_path for media assets (video/image/voice).
    """
    asset_type_map = {
        "write_script": "script",
        "render_image": "image_path",
        "render_video": "video_path",
        "tts": "voice_path",
        "ideate": "idea",
    }
    asset_type = asset_type_map.get(action)
    if not asset_type:
        return None
    try:
        q = sb.table("asset_library").select("*").eq("asset_type", asset_type)
        if account_id:
            q = q.or_(f"account_id.eq.{account_id},account_id.is.null")
        r = q.limit(5).order("performance_score", desc=True).execute()
        candidates = [c for c in (r.data or []) if c.get("performance_score", 0 if c.get("performance_score") is not None else 0.7) >= 0.6]
        if candidates:
            # bump usage_count
            best = candidates[0]
            # If it's a media asset and blob_path/path no longer exists, skip
            if asset_type in ("video_path","image_path","voice_path"):
                path = best.get("blob_path") or best.get("content")
                if path and not os.path.exists(path):
                    return None
            sb.table("asset_library").update({"usage_count": (best.get("usage_count") or 0)+1,
                                              "last_used_at": datetime.datetime.utcnow().isoformat()}).eq("id", best["id"]).execute()
            return best
    except Exception:
        return None
    return None


def _store_asset(sb, asset_type: str, content: str, account_id=None, niche: str = "", cost: float = 0, tags: List[str] = None, perf_score: float = None, blob_path: str = None):
    """Store content as a reusable asset in asset_library (keyed by hash).
    v5.5 P0 FIX: supports blob_path for media files (video/image/voice) and upserts
    so repeated calls don't duplicate.
    """
    # Content keyed by hash of (type + content/blob_path + niche) so identical content dedupes
    key_src = f"{asset_type}|{niche}|{content}|{blob_path or ''}"
    content_hash = hashlib.sha256(key_src.encode("utf-8")).hexdigest()[:16]
    try:
        existing = sb.table("asset_library").select("id,usage_count").eq("id", content_hash).execute()
        if existing.data:
            # Bump usage count instead of duplicating
            cur = existing.data[0]
            sb.table("asset_library").update({
                "usage_count": (cur.get("usage_count") or 0) + 1,
                "last_used_at": datetime.datetime.utcnow().isoformat(),
            }).eq("id", content_hash).execute()
            return content_hash
        row = {
            "id": content_hash, "tenant_id":"me",
            "account_id": str(account_id) if account_id else None,
            "niche": niche or None, "asset_type": asset_type,
            "content": content if content and len(content) < 10000 else (content[:10000] if content else ""),
            "tags": tags or [], "usage_count": 1,
            "performance_score": perf_score,
            "cost_to_make_usd": cost,
        }
        if blob_path:
            row["blob_path"] = blob_path
        sb.table("asset_library").insert(row).execute()
        return content_hash
    except Exception:
        traceback.print_exc()
        return None


def _record_revenue(sb, account_id, item_id, amount_usd: float, source: str, metadata: dict = None):
    """v5.5 P0: insert a revenue_events row so roi_snapshots can compute real revenue."""
    try:
        sb.table("revenue_events").insert({
            "tenant_id": "me",
            "account_id": str(account_id) if account_id else None,
            "item_id": str(item_id) if item_id else None,
            "amount_usd": round(float(amount_usd), 5),
            "source": source,
            "metadata": metadata or {},
        }).execute()
    except Exception:
        traceback.print_exc()


def _expected_value(sb, account_id, action: str, cost: float, default_cfg: dict) -> float:
    """Return expected revenue in USD for running this action for this account."""
    try:
        # Use recent ROI for this account: revenue per post * probability of producing a post
        today = datetime.date.today()
        week_ago = today - datetime.timedelta(days=7)
        r = sb.table("roi_snapshots").select("revenue_usd,posts_published,spend_usd").eq("account_id", str(account_id)).gte("day", week_ago.isoformat()).execute()
        rows = r.data or []
        if rows and sum(x.get("posts_published",0) for x in rows) > 0:
            total_rev = sum(x.get("revenue_usd",0) for x in rows)
            total_posts = sum(x.get("posts_published",0) for x in rows)
            rev_per_post = total_rev / max(1, total_posts)
            # A write_script leads to a post ~ 30% of the time (after grading and render)
            prob_post = {"ideate":0.6,"write_script":0.4,"grade_script":0.9,"render_image":0.85,
                         "render_video":0.9,"edit_video":0.95,"tts":0.95,"distribute":1.0}.get(action,0.5)
            return rev_per_post * prob_post
    except Exception:
        pass
    return default_cfg.get("ev", cost * 1.5)


def _success_probability(sb, account_id, action: str) -> float:
    """P(success) — probability this action produces a usable result."""
    base = {"scout":0.99,"ideate":0.9,"write_script":0.75,"grade_script":0.99,
            "render_image":0.85,"tts":0.98,"render_video":0.6,"edit_video":0.9,
            "caption_burn":0.99,"distribute":0.95,"reply_comments":0.9,"brand_studio":0.9,"analyze":0.99}.get(action,0.8)
    return base


def _cheaper_alternative(action: str, cost: float, cfg: dict) -> Optional[str]:
    """If this action has a free/cheap version, return the model_tier to try."""
    if cfg.get("free_tier_preferred", True):
        if action in ("write_script","ideate","grade_script","reply_comments","brand_studio","analyze"):
            return "free" if cost > 0.005 else None
        if action == "render_image": return "free"   # Gemini 2.5 Flash image is free
        if action == "tts": return "free"           # Gemini TTS free
    return None


def _account_roi(sb, account_id) -> Optional[float]:
    """Lifetime ROI multiple for an account. None = cold start (no data yet)."""
    if not account_id: return None
    try:
        r = sb.table("roi_snapshots").select("revenue_usd,spend_usd")
        # filter service-side
        r = r.eq("account_id", str(account_id)).limit(30).execute()
        rows = r.data or []
        if not rows: return None
        total_rev = sum(x.get("revenue_usd",0) for x in rows)
        total_spend = sum(x.get("spend_usd",0) for x in rows)
        if total_spend <= 0: return 9.99 if total_rev > 0 else None
        return round(total_rev / total_spend, 2)
    except Exception:
        return None


def _losing_streak(sb, account_id) -> int:
    """Consecutive days where revenue < spend (0 = profitable or no data)."""
    if not account_id: return 0
    try:
        today = datetime.date.today()
        r = sb.table("roi_snapshots").select("revenue_usd,spend_usd,day")
        r = r.eq("account_id", str(account_id)).order("day", desc=True).limit(7).execute()
        rows = r.data or []
        streak = 0
        for x in rows:
            if (x.get("revenue_usd") or 0) < (x.get("spend_usd") or 0):
                streak += 1
            else:
                break
        return streak
    except Exception:
        return 0


def _snapshot_roi(sb):
    """Roll up run_ledger + performance + revenue into today's roi_snapshots rows."""
    today = datetime.date.today().isoformat()
    try:
        # All active accounts
        accs = sb.table("project_accounts").select("id").eq("paused", False).execute().data or []
        for a in accs:
            aid = str(a["id"])
            # Spend
            r = sb.table("run_ledger").select("cost_usd,step,department,created_at")
            r = r.eq("account_id", aid).gte("created_at", today).execute()
            spend = sum(float(x.get("cost_usd") or 0) for x in (r.data or []))
            # Count actions by step
            actions = {}
            for x in (r.data or []):
                s = x.get("step","?"); actions[s] = actions.get(s,0)+1
            # Performance (views/likes etc.)
            p = sb.table("performance").select("views,likes,comments,shares,saves,follows")
            p = p.eq("account_id", aid).gte("created_at", today).execute()
            perf = p.data or []
            views    = sum(x.get("views",0) or 0 for x in perf)
            likes    = sum(x.get("likes",0) or 0 for x in perf)
            comments = sum(x.get("comments",0) or 0 for x in perf)
            shares   = sum(x.get("shares",0) or 0 for x in perf)
            saves    = sum(x.get("saves",0) or 0 for x in perf)
            followers= sum(x.get("follows",0) or 0 for x in perf)
            # Revenue: sum of revenue_events for this account today (v5.5 P0)
            revenue = 0.0
            try:
                rev = sb.table("revenue_events").select("amount_usd").eq("account_id", aid).gte("created_at", today).execute()
                revenue = round(sum(float(x.get("amount_usd") or 0) for x in (rev.data or [])), 5)
            except Exception:
                pass
            # Upsert snapshot
            sb.table("roi_snapshots").upsert({
                "tenant_id":"me","account_id":aid,"day":today,
                "spend_usd":round(spend,5),
                "posts_published":actions.get("distribute",0),
                "scripts_written":actions.get("brain",0)+actions.get("write_script",0),
                "images_generated":actions.get("visuals",0),
                "videos_generated":actions.get("render_video",0),
                "views":views,"likes":likes,"comments":comments,"shares":shares,"saves":saves,"followers_gained":followers,
                "revenue_usd":revenue,
                "roi_multiple": round(revenue/spend,2) if spend>0 else None,
                "cost_per_view": round(spend/views,6) if views>0 else None,
                "cost_per_follower": round(spend/followers,4) if followers>0 else None,
                "cost_per_engagement": round(spend/(likes+comments+shares+saves),4) if (likes+comments+shares+saves)>0 else None,
            }, on_conflict="tenant_id,account_id,day").execute()
    except Exception:
        traceback.print_exc()


def _allocate_budgets(sb, bus) -> int:
    """Allocate daily budgets per account based on ROI. Returns # of accounts updated."""
    try:
        cfg = _load_config(sb)
        total_budget = float(cfg.get("global_daily_budget") or float(os.environ.get("DAILY_BUDGET_USD","1.50")))
        # Fetch accounts
        accs = sb.table("project_accounts").select("id,daily_budget_usd,paused,niche,name").execute().data or []
        # Compute ROI score per account
        scored = []
        for a in accs:
            if a.get("paused"): continue
            roi = _account_roi(sb, a["id"])
            streak = _losing_streak(sb, a["id"])
            days_alive = 1
            scored.append({**a, "roi": roi or 1.0, "streak": streak, "cold": roi is None})
        if not scored: return 0
        # Weights: cold starts get new_account_daily_budget, losers get paused, winners get scaled
        cold_budget = float(cfg.get("new_account_daily_budget", 0.25))
        n_cold = sum(1 for s in scored if s["cold"])
        n_winners = sum(1 for s in scored if not s["cold"] and s["roi"] >= 1.0)
        n_losers = sum(1 for s in scored if not s["cold"] and s["roi"] < 1.0)
        # Reserve 10% reserve
        reserve = total_budget * float(cfg.get("reserve_fraction",0.1))
        pool = total_budget - reserve - (n_cold * cold_budget)
        per_winner = pool / max(1, n_winners) if n_winners else 0
        today = datetime.date.today().isoformat()
        updates = 0
        for s in scored:
            focus = "balanced"; posts = 2; budget = s.get("daily_budget_usd")
            model_tier = "mix"
            note = ""
            if s["cold"]:
                budget = cold_budget; posts = 2; focus = "grow"; model_tier = "free"
                note = f"cold-start: {cold_budget:.2f} using free/cheap models"
            elif s["streak"] >= int(cfg.get("pause_losers_after_days",3)):
                budget = 0.0; posts = 0; focus = "pause"; model_tier = "free"
                note = f"paused: ROI {s['roi']:.2f}x for {s['streak']} days"
                sb.table("project_accounts").update({"paused": True}).eq("id", s["id"]).execute()
            elif s["roi"] >= 3.0:
                budget = per_winner * 1.5; posts = 5; focus = "grow"; model_tier = "mix"
                note = f"scaling winner (ROI {s['roi']:.2f}x) → ${budget:.2f}, up to {posts} posts"
            elif s["roi"] >= 1.0:
                budget = per_winner; posts = 3; focus = "balanced"; model_tier = "mix"
                note = f"profitable (ROI {s['roi']:.2f}x) → ${budget:.2f}, {posts} posts"
            else:
                budget = per_winner * 0.3; posts = 1; focus = "profit"; model_tier = "cheap"
                note = f"weak ROI {s['roi']:.2f}x — cut to ${budget:.2f}, {posts} post, cheap models only"
            sb.table("capital_allocation").upsert({
                "tenant_id":"me","account_id":s["id"],"day":today,
                "budget_usd":round(budget,2),"max_posts":posts,
                "focus":focus,"model_tier":model_tier,"note":note,"approved_by":"ceo",
            }, on_conflict="tenant_id,account_id,day").execute()
            bus.agent("coo", f"📊 {s.get('name','?')}: {note}", "info", "alloc", account_id=s["id"])
            updates += 1
        return updates
    except Exception:
        traceback.print_exc()
        return 0


def _write_recommendations(sb) -> int:
    """Generate 3-7 actionable ceo_recommendations for the human."""
    recs: List[dict] = []
    today = datetime.date.today().isoformat()
    try:
        # Clear any open recommendations older than today
        sb.table("ceo_recommendations").update({"dismissed": True}).lt("day", today).execute()
        # Build recs from ROI data
        accs = sb.table("project_accounts").select("id,name,niche,paused,daily_budget_usd").execute().data or []
        alloc = sb.table("capital_allocation").select("*").eq("day", today).execute().data or []
        alloc_by_acc = {str(a["account_id"]): a for a in alloc}
        for a in accs:
            aid = str(a["id"]); name = a.get("name","account")
            al = alloc_by_acc.get(aid, {})
            roi = _account_roi(sb, aid)
            streak = _losing_streak(sb, aid)
            if al.get("focus") == "pause":
                recs.append({"severity":"critical","category":"pause",
                    "account_id":aid,"recommendation":f"⏸ PAUSE {name}",
                    "reasoning":f"ROI {roi:.2f}x for {streak} straight days. Spend is producing no revenue. Paused automatically.",
                    "projected_roi":0.0,"projected_value_usd":al.get("budget_usd",0),
                    "action_url":f"/b/{aid}"})
            elif al.get("focus") == "grow" and (roi or 0) >= 3:
                extra = (al.get("budget_usd") or 0) * 0.4
                recs.append({"severity":"opportunity","category":"scale",
                    "account_id":aid,"recommendation":f"🚀 Scale {name} — +40% budget",
                    "reasoning":f"Winning account at {roi:.2f}x ROI. Historical data supports increasing spend to capture more audience.",
                    "projected_roi":roi,"projected_value_usd":extra*roi,
                    "action_url":f"/b/{aid}"})
            elif al.get("focus") == "profit" and (roi or 9) < 1 and streak >= 2:
                recs.append({"severity":"action","category":"content",
                    "account_id":aid,"recommendation":f"🔍 Review {name} — weak ROI, try evergreen reuse",
                    "reasoning":f"ROI {roi:.2f}x. Recommend reusing proven hooks instead of generating fresh scripts for 3 days.",
                    "projected_roi":2.0,"projected_value_usd":(al.get("budget_usd") or 0)*2,
                    "action_url":f"/b/{aid}"})
        # Cross-account recs
        total_spend = 0
        rows = sb.table("run_ledger").select("cost_usd").gte("created_at", today).execute().data or []
        total_spend = sum(float(x.get("cost_usd") or 0) for x in rows)
        budget = float(os.environ.get("DAILY_BUDGET_USD","1.50"))
        if total_spend < budget * 0.5:
            recs.append({"severity":"action","category":"budget",
                "recommendation":f"💰 Budget underused (${total_spend:.2f}/${budget:.2f})",
                "reasoning":"Less than 50% of daily budget spent by mid-day. Consider producing 1-2 extra posts for your winning account or running an A/B test on hooks.",
                "projected_roi":1.5,"projected_value_usd":(budget-total_spend)*1.5})
        if total_spend > budget * 0.9:
            recs.append({"severity":"critical","category":"budget",
                "recommendation":f"⚠️ Near budget cap (${total_spend:.2f}/${budget:.2f})",
                "reasoning":"At 90% of daily spend. Agents will auto-fallback to free models within the hour.",
                "projected_roi":0.0,"projected_value_usd":0})
        # Always give a reusable content recommendation
        recs.append({"severity":"info","category":"reuse",
            "recommendation":"♻️ Search asset library before generating",
            "reasoning":"Your CEO engine is configured to prefer reusing proven scripts, hooks, and visuals over generating fresh content. This cuts spend by 30-60% with no quality loss.",
            "projected_roi":2.0,"projected_value_usd":total_spend*0.4})
        # Write them
        for r in recs:
            sb.table("ceo_recommendations").insert({
                "tenant_id":"me","day":today,**r
            }).execute()
        return len(recs)
    except Exception:
        traceback.print_exc()
        return 0
