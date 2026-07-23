"""departments/strategy.py — v5.8.8

Two jobs, both born from the founder's spend policy of 2026-07-23:

  strategy.audit   The ONLY paid thinking call in the system. Once every N days
                   (default 10) Anthropic reads the whole period — what shipped,
                   what got rejected and why, what the graders said, what it
                   cost — and writes lessons back into memory so the free models
                   that do the daily work get better. One call. ~$0.05.

  strategy.arena_scout   Pulls the live arena.ai leaderboards (text, text-to-image,
                   text-to-video, image-to-video) and stores the rankings, with the
                   open-weight subset called out. It then rewrites
                   settings.free_council_models so the free debate roster follows
                   the leaderboard without a redeploy.

Why the scout matters: on 2026-07-23 the council was still pointed at
"moonshotai/kimi-k2:free", a route OpenRouter had removed. Every draft through
that provider failed and silently fell through to paid Claude. A roster that
verifies itself against the live model list prevents that class of bug.
"""
from __future__ import annotations
import json, re, time, urllib.request

from agentcore import Worker, Job, AgentContext, Priority
from agentcore import costmode

ARENAS = {
    "text":           "https://arena.ai/leaderboard/text",
    "text_to_image":  "https://arena.ai/leaderboard/text-to-image",
    "text_to_video":  "https://arena.ai/leaderboard/text-to-video",
    "image_to_video": "https://arena.ai/leaderboard/image-to-video",
    "image_edit":     "https://arena.ai/leaderboard/image-edit",
}
UA = {"User-Agent": "Mozilla/5.0 (compatible; AgentX/5.8.8; +leaderboard-scout)"}
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"


def _fetch(url: str, headers: dict = None, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _parse_arena(html: str, limit: int = 60) -> list:
    """arena.ai ships its table inside an escaped-JSON RSC payload. Parse the
    row objects out of it. Returns [] if the page shape changed — we never
    invent rankings."""
    u = html.replace('\\"', '"')
    rows, seen = [], set()
    for m in re.finditer(r'\{"rank":(\d+),"rankUpper".{0,900}?"license":"([^"]+)"', u):
        seg = m.group(0)
        name = re.search(r'"modelDisplayName":"([^"]+)"', seg)
        rating = re.search(r'"rating":([\d.]+)', seg)
        org = re.search(r'"modelOrganization":"([^"]+)"', seg)
        if not name or name.group(1) in seen:
            continue
        seen.add(name.group(1))
        rows.append({"rank": int(m.group(1)), "model": name.group(1),
                     "elo": round(float(rating.group(1)), 1) if rating else None,
                     "org": org.group(1) if org else None,
                     "license": m.group(2),
                     "open": m.group(2).lower() != "proprietary"})
    rows.sort(key=lambda r: r["rank"])
    return rows[:limit]


def _free_openrouter_routes() -> list:
    """The routes OpenRouter actually serves for $0 right now."""
    try:
        d = json.loads(_fetch(OPENROUTER_MODELS))
        return sorted(m["id"] for m in d.get("data", []) if m.get("id", "").endswith(":free"))
    except Exception:
        return []


def arena_scout(w: Worker, job: Job, ctx: AgentContext):
    _bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    boards, notes = {}, []
    for name, url in ARENAS.items():
        try:
            rows = _parse_arena(_fetch(url))
            boards[name] = rows
            if not rows:
                notes.append(f"{name}: page shape changed, no rows parsed")
        except Exception as e:
            boards[name] = []
            notes.append(f"{name}: {str(e)[:80]}")

    free_routes = _free_openrouter_routes()

    # Build the free debate roster: Gemini + Groq (own free tiers) plus the
    # highest-ranked open-weight models that OpenRouter actually serves free.
    roster = [{"provider": "gemini", "model": "gemini-2.5-flash", "why": "free tier"},
              {"provider": "groq", "model": "llama-3.3-70b-versatile", "why": "free tier"}]
    # The overall board is dominated by proprietary models — the first
    # open-weight entry sits around #29. Fetch the open-source-filtered board
    # too so the free roster is chosen from a real open-weight ranking.
    # NOTE: arena.ai applies its ?license= filter client-side, so the payload is
    # the same either way — we filter on the parsed rows instead. The first
    # open-weight entry sits around #29 overall, hence the 60-row window.
    open_rows = [r for r in (boards.get("text") or []) if r["open"]]
    boards["text_open_weight"] = open_rows[:15]
    for r in open_rows:
        stem = re.split(r"[ (]", r["model"].lower())[0]
        for route in free_routes:
            if stem and stem in route.lower():
                roster.append({"provider": "openrouter", "model": route,
                               "why": f"arena #{r['rank']} open-weight ({r['license']})"})
                break
        if len(roster) >= 5:
            break
    for route in free_routes:                       # top up if arena matching was thin
        if len(roster) >= 5:
            break
        if not any(x["model"] == route for x in roster):
            roster.append({"provider": "openrouter", "model": route, "why": "free route"})

    if sb is not None:
        try:
            sb.table("settings").upsert(
                {"tenant_id": _tenant(), "key": "arena_rankings",
                 "value": {"boards": boards, "free_openrouter_routes": free_routes,
                           "checked_at": time.time(), "notes": notes}},
                on_conflict="tenant_id,key").execute()
            sb.table("settings").upsert(
                {"tenant_id": _tenant(), "key": "free_council_models",
                 "value": {"models": roster, "source": "arena.ai + openrouter live model list",
                           "updated_at": time.time()}},
                on_conflict="tenant_id,key").execute()
        except Exception:
            pass

    top_open = ", ".join(f"{r['model']} (#{r['rank']})" for r in open_rows[:3]) or "none parsed"
    _bus.agent("cto", f"🏆 arena scout — top open-weight text: {top_open} · "
                     f"{len(free_routes)} free OpenRouter routes live · "
                     f"free council roster now {len(roster)} models"
                     + (f" · notes: {'; '.join(notes)}" if notes else ""),
              "info", "arena_scout", job_id=job.id)

    try:
        w.queue.enqueue(Job(job_type="strategy.arena_scout", payload={"scheduled": True},
                            priority=Priority.LOW, scheduled_for=time.time() + 7 * 86400,
                            idempotency_key=f"arena:{int(time.time() // (7 * 86400))}"))
    except Exception:
        pass
    w.queue.complete(job, {"ok": True, "boards": {k: len(v) for k, v in boards.items()},
                           "free_routes": len(free_routes), "roster": roster})


AUDIT_PROMPT = """You are the strategy auditor for a faceless short-form content system.
This is the ONE paid review in a {days}-day cycle — everything else was produced by
free open-weight models debating each other. Your job is to make those free models
better, not to rewrite their work.

PERIOD DATA
{data}

Return STRICT JSON, no markdown:
{{
 "verdict": "<2 sentences: is this system actually producing publishable work?>",
 "biggest_leak": "<the single costliest or most-blocking problem, with the evidence>",
 "lessons": ["<= 6 concrete, reusable instructions for the writing/grading models. Each must be specific enough to change a draft>"],
 "stop_doing": ["<= 3 things wasting time or money>"],
 "next_period_focus": "<one sentence>"
}}
Be blunt. No praise. No income claims. If the data shows nothing shipped, say so plainly."""


def audit(w: Worker, job: Job, ctx: AgentContext):
    """strategy.audit — the only paid thinking call. Skips itself if not due."""
    _bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    forced = bool(job.payload.get("force"))
    if not forced and not costmode.audit_due():
        _bus.agent("ceo", "strategy audit not due yet — skipping (policy: paid thinking "
                         "only once per cycle)", "info", "audit_skip", job_id=job.id)
        w.queue.complete(job, {"ok": True, "skipped": "not_due"})
        return
    if not costmode.has_key("anthropic"):
        _bus.agent("ceo", "strategy audit skipped — no ANTHROPIC_API_KEY", "warn",
                  "audit_skip", job_id=job.id)
        w.queue.complete(job, {"ok": True, "skipped": "no_key"})
        return

    days = float(costmode.policy().get("strategy_audit_days", 10) or 10)
    since = time.time() - days * 86400
    import datetime as _dt
    since_iso = _dt.datetime.utcfromtimestamp(since).isoformat() + "Z"
    data = {}
    if sb is not None:
        try:
            items = (sb.table("board_items").select("status")
                     .gte("created_at", since_iso).execute().data) or []
            counts = {}
            for it in items:
                counts[it.get("status")] = counts.get(it.get("status"), 0) + 1
            data["items_by_status"] = counts
            led = (sb.table("run_ledger").select("model,cost_usd,step")
                   .gte("created_at", since_iso).execute().data) or []
            spend = {}
            for r in led:
                m = r.get("model") or "unknown"
                spend[m] = round(spend.get(m, 0) + float(r.get("cost_usd") or 0), 4)
            data["spend_by_model"] = spend
            data["total_spend_usd"] = round(sum(spend.values()), 4)
            les = (sb.table("agent_lessons").select("kind,content")
                   .gte("created_at", since_iso).limit(60).execute().data) or []
            data["recent_lessons"] = [f"{l.get('kind')}: {(l.get('content') or '')[:180]}"
                                      for l in les]
        except Exception as e:
            data["data_error"] = str(e)[:200]

    prompt = AUDIT_PROMPT.format(days=int(days), data=json.dumps(data, indent=1)[:8000])
    try:
        from agentcore import aisuite
        text, meta = aisuite.generate_text(prompt, model="claude-sonnet-4-5", max_tokens=1200)
        from agentcore import ledger as _led
        _led.record("strategy.audit", model=meta.get("model"), cost_usd=meta.get("cost_usd", 0))
        parsed = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except Exception as e:
        _bus.agent("ceo", f"strategy audit failed: {str(e)[:120]}", "warn",
                  "audit_error", job_id=job.id)
        w.queue.complete(job, {"ok": False, "error": str(e)[:200]})
        return

    # Feed the lessons back to the free models that do the daily work.
    try:
        from agentcore import memory as _m
        for lesson in (parsed.get("lessons") or [])[:6]:
            _m.add_lesson("strategy_audit", str(lesson)[:400],
                          metadata={"period_days": days, "source": "anthropic_audit"})
    except Exception:
        pass

    costmode.mark_audit_done(json.dumps(parsed)[:2000])
    if sb is not None:
        try:
            sb.table("settings").upsert(
                {"tenant_id": _tenant(), "key": "strategy_audit_latest",
                 "value": {"at": time.time(), "period_days": days,
                           "report": parsed, "data": data}},
                on_conflict="tenant_id,key").execute()
        except Exception:
            pass

    _bus.agent("ceo", f"🧠 {int(days)}-day strategy audit (Anthropic, 1 paid call): "
                     f"{parsed.get('verdict', '')[:200]} · biggest leak: "
                     f"{parsed.get('biggest_leak', '')[:160]} · "
                     f"{len(parsed.get('lessons') or [])} lessons written to memory",
              "success", "strategy_audit", job_id=job.id)

    try:
        w.queue.enqueue(Job(job_type="strategy.audit", payload={"scheduled": True},
                            priority=Priority.LOW, scheduled_for=time.time() + days * 86400,
                            idempotency_key=f"audit:{int(time.time() // (days * 86400))}"))
    except Exception:
        pass
    w.queue.complete(job, {"ok": True, "report": parsed})


def _tenant():
    try:
        from agentcore import config as _cfg
        return _cfg.TENANT_ID
    except Exception:
        import os
        return os.environ.get("TENANT_ID", "me")


def register(w: Worker):
    w.register("strategy.audit", audit)
    w.register("strategy.arena_scout", arena_scout)
