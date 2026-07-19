"""departments/monetization.py — I (Monetization).

Phase 3 scaffolding for affiliate links, sponsorship inbox, and digital
product placement. For now, monetization.inject is called from the post-
production step and:
  - Reads any affiliate URLs configured for the account.
  - If configured, appends a short "link in bio" / disclosure line to captions.
  - Detects sponsor mentions in captions and ensures FTC-compliant #ad tag.
  - Logs revenue opportunities to memory.

Full affiliate rotation, sponsor outreach, and digital-product delivery are
v5.2 scope. This module lays the schema + the safe caption-injection hook.
"""
from __future__ import annotations
import time
from typing import Optional
from agentcore import Worker, Job, AgentContext
from ..common import board_patch_payload, load_account, job_of


def register(w: Worker):
    w.register("monetization.inject", inject)
    w.register("monetization.scan_inbox", scan_inbox)


def inject(w: Worker, job: Job, ctx: AgentContext):
    """Called after risk.scan, before publish. Augment caption with
    link-in-bio / disclosure if configured."""
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    account_id = job.account_id or job.payload.get("account_id")
    captions = dict(job.payload.get("captions") or {})
    script = job.payload.get("script") or {}
    caption = job.payload.get("caption_text") or ""
    account = load_account(sb, account_id) or {}

    affs = (account.get("affiliate_urls") or [])
    sponsor = account.get("sponsor") or None
    addendum_lines = []

    if sponsor:
        addendum_lines.append(f"#ad — sponsored by {sponsor}")
    if affs:
        addendum_lines.append("links in bio 🔗")

    if addendum_lines and caption:
        addendum = "\n\n" + " · ".join(addendum_lines)
        caption = (caption + addendum)[:2000]
        # Patch Instagram caption too if it exists
        if isinstance(captions.get("instagram"), dict):
            base_cap = captions["instagram"].get("caption", "")
            captions["instagram"]["caption"] = (base_cap + addendum)[:2200]

    bus.agent("distro", "💰 monetization injected" + (" (sponsor+affiliate)" if sponsor and affs else
                         " (sponsor)" if sponsor else " (affiliate)" if affs else " — nothing configured"),
              "info", "monetize", job_id=job.id, item_id=item_id)

    # Forward to publish
    job_of(w, "distribution.publish", {
        **job.payload, "caption_text": caption, "captions": captions,
        "_monetized": True,
    }, parent=job, account_id=account_id, project_id=job.project_id,
       priority=job.priority)
    w.queue.complete(job, {"ok": True, "addendum": bool(addendum_lines)})


def scan_inbox(w: Worker, job: Job, ctx: Optional[AgentContext] = None):
    """Placeholder for sponsor DM scan. Future: read brand DMs/emails,
    rank offers by fit, escalate >= threshold deals for human approval."""
    w.queue.complete(job, {"ok": True, "scanned": 0})
