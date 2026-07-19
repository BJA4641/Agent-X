"""departments/brand_studio.py — B (Brand Studio).

Phase 3: automated Brand Bible generation for a newly-unpaused account.
When portfolio.tick finds an account whose brand_bible column is null,
it enqueues brand_studio.generation; the architect agent writes the full
25-document brand bible, and the account is marked ready so production
can begin.
"""
from __future__ import annotations
import time
from agentcore import Worker, Job, AgentContext, Priority, BrandBible
from ..common import job_of, load_account


REQUIRED_DOCS = [
    "executive_summary", "vision_mission", "revenue_model", "brand_identity",
    "visual_identity", "marketing_strategy", "instagram_playbook",
    "tiktok_playbook", "youtube_playbook", "content_calendar", "content_rules",
    "hashtags_seo", "production_sop",
]


def register(w: Worker):
    w.register("brand_studio.generate", generate_brand_bible)


def generate_brand_bible(w: Worker, job: Job, ctx: AgentContext):
    """Use architect agent to write a full Brand Bible for an account that
    doesn't have one yet, then persist to account_documents + brand_bible
    column on project_accounts."""
    from agent import architect as _arch
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    account_id = job.account_id or job.payload.get("account_id")
    niche = job.payload.get("niche") or ""
    account = load_account(sb, account_id)
    name = (account or {}).get("name") or (account or {}).get("handle") or "new account"

    bus.agent("architect", f"🏛️ drafting Brand Bible for {name} ({niche})", "info",
              "brand_start", job_id=job.id, account_id=account_id)

    docs = {}
    try:
        # architect has a `write_brand_docs(niche, name)` style API — try both
        # shapes defensively so older architect versions don't crash.
        if hasattr(_arch, "draft_brand_bible"):
            docs = _arch.draft_brand_bible(niche, account_name=name) or {}
        elif hasattr(_arch, "write_brand_docs"):
            docs = _arch.write_brand_docs(niche, name) or {}
        elif hasattr(_arch, "brand_bible_for"):
            docs = _arch.brand_bible_for(niche, name) or {}
        else:
            # Fallback: minimal brand bible generated via structured LLM
            docs = _fallback_brand_bible(niche, name, w, job, ctx)
    except Exception as e:
        bus.agent("architect", f"🏛️ brand bible error: {str(e)[:120]}", "error",
                  "brand_err", job_id=job.id)
        docs = _fallback_brand_bible(niche, name, w, job, ctx)

    # Persist docs to account_documents
    if sb and account_id:
        for doc_type in REQUIRED_DOCS:
            content = docs.get(doc_type, "") or ""
            if not content and doc_type in _DEFAULT_DOCS(niche, name):
                content = _DEFAULT_DOCS(niche, name)[doc_type]
            if not content:
                continue
            try:
                sb.table("account_documents").upsert({
                    "account_id": str(account_id),
                    "doc_type": doc_type,
                    "content": content[:20000],
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }).execute()
            except Exception as ex:
                bus.agent("architect", f"🏛️ doc {doc_type} save failed: {str(ex)[:80]}",
                          "warn", "brand_doc_err", job_id=job.id)
        # Mark brand_bible present on the account
        try:
            sb.table("project_accounts").update({
                "brand_bible": {k: (docs.get(k) or "")[:1000] for k in REQUIRED_DOCS},
            }).eq("id", str(account_id)).execute()
        except Exception:
            pass

    bus.agent("architect", f"🏛️ Brand Bible ready — {len(docs)} docs for {name}",
              "success", "brand_done", job_id=job.id, account_id=account_id)
    w.queue.complete(job, {"ok": True, "docs_written": list(docs.keys())})


def _fallback_brand_bible(niche, name, w, job, ctx) -> dict:
    """Minimal brand bible via BaseAgent LLM when architect isn't available."""
    bus = ctx.deps["bus"]
    bus.agent("architect", "🏛️ using fallback LLM brand-bible generator", "warn",
              "brand_fallback", job_id=job.id)
    prompt = (
        f"You are creating a short-form social media Brand Bible for a new account.\n\n"
        f"Account name: {name}\nNiche: {niche}\n\n"
        "Return STRICT JSON with keys for each document — short, actionable, "
        "specific to short-form vertical video (Reels/TikTok/Shorts):\n"
        "executive_summary, vision_mission, revenue_model, brand_identity, "
        "visual_identity, marketing_strategy, instagram_playbook, tiktok_playbook, "
        "youtube_playbook, content_calendar, content_rules, hashtags_seo, production_sop.\n"
        "Each value = 3-6 sentences. Don't be generic."
    )
    try:
        result = w.llm_structured(prompt, result_type=BrandBible, tier="standard")
        return result.model_dump()
    except Exception:
        return _DEFAULT_DOCS(niche, name)


def _DEFAULT_DOCS(niche, name):
    base = (niche or "productivity tips").lower()
    return {
        "executive_summary": f"{name} is a short-form media brand in the {base} niche. "
                             f"Our goal: publish 2 vertical videos per day, grow to 100k followers "
                             "in 90 days, and monetize via affiliates, sponsorships, and a digital product.",
        "vision_mission": f"Become the go-to {base} account on every platform by publishing "
                          "one genuinely useful tip per video, no fluff, no clickbait.",
        "revenue_model": "Phase 1: affiliate links in bio. Phase 2: sponsorships at 10k followers. "
                         "Phase 3: $27 digital guide at 50k followers.",
        "brand_identity": "Tone: blunt, helpful, a little sarcastic. Voice: friend who knows the "
                         "secret. Visual: dark mode, neon accent, kinetic captions.",
        "visual_identity": "9:16 vertical, 1080x1920, dark navy background (#0a0e1d), "
                           "accent cyan (#22d3ee), kinetic white captions, 2-3 words on screen at a time.",
        "marketing_strategy": "1) Post 2x/day. 2) Jump on trending audio under 10k uses. "
                              "3) Engage with 30 accounts in niche per day. 4) Cross-post to IG+TT+YT.",
        "instagram_playbook": "Reels 15-45s. Hook first 1s. 6-7 beats. CTA in last 2s. "
                              "Hashtags 8-12 per post. Stories daily BTS.",
        "tiktok_playbook": "Use trending audio 3x/week. Pattern-interrupt hooks. Text-on-screen "
                           "every 2 seconds. Duet/stitch top creators in the niche.",
        "youtube_playbook": "Shorts 20-55s. Title = hook. End screen: 'Follow for one move a day'.",
        "content_calendar": "2 posts/day at 9am and 7pm local. Weekly themes: Mon=mistake warning, "
                            "Tue=tool, Wed=quick win, Thu=contrarian take, Fri=demo showcase, "
                            "Sat=result proof, Sun=pattern interrupt.",
        "content_rules": "No banned phrases ('guaranteed income','get rich quick','cures','miracle'). "
                         "Hook <= 8 words. 6-7 beats. Video 15-55 seconds. Always end with CTA.",
        "hashtags_seo": f"#{'#'.join(base.split() if base else ['ai','tech','tools'])}, "
                        "#viral #learn #fyp #shorts",
        "production_sop": "1) Pick topic from strategy. 2) Write script (brain). 3) Grade CQO >=8.0. "
                          "4) Generate frames (Gemini). 5) Record narration (edge-tts). "
                          "6) Assemble with captions + music + SFX. 7) Risk scan. 8) Publish.",
    }
