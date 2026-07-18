"""digest.py — the strategy agent reports to its boss. Weekly numbers + one
recommendation. Saved to settings (Studio renders it); emailed if RESEND key exists."""
import json, time, datetime
from . import config, ledger, board

def _views(item):
    m = item["payload"].get("metrics", {})
    return sum(v.get("views", 0) for v in m.values())

def build_data() -> dict:
    week_ago = time.time() - 7 * 86400
    def recent(st):
        return [i for i in board.list(st) if _ts(i) >= week_ago]
    pub = recent("published") + recent("reported")
    buckets = {}
    for i in board.list("reported"):
        b = i["payload"].get("bucket", "unknown")
        buckets.setdefault(b, []).append(_views(i))
    from collections import Counter
    rejections = Counter((i["payload"].get("rejection") or {}).get("reason", "")
                         for i in board.list("rejected") if i["payload"].get("rejection"))
    best = max(pub, key=_views) if pub else None
    return {
        "published_this_week": len(pub),
        "total_views_this_week": sum(_views(i) for i in pub),
        "best_clip": {"topic": best["topic"], "views": _views(best)} if best else None,
        "bucket_avg_views": {b: round(sum(v) / len(v)) for b, v in buckets.items() if v},
        "spend_usd_this_week": round(ledger.spent_since(7), 4),
        "top_rejection_reasons": dict(rejections.most_common(3)),
        "hook_picks": sum(1 for i in board.list() if i["payload"].get("hook_choice")),
    }

def _ts(item):
    for k in ("updated_at", "created_at"):
        v = item.get(k)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
    return 0

def compose(data: dict) -> str:
    if config.HAS_ANTHROPIC and ledger.budget_ok(0.008):
        try:
            import anthropic
            prompt, version = config.load_prompt("digest_v1")
            prompt = prompt.replace("{data}", json.dumps(data))
            msg = anthropic.Anthropic().messages.create(
                model=config.get("CLAUDE_MODEL", "claude-sonnet-4-5"), max_tokens=400,
                messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in msg.content if b.type == "text").strip()
            cost = (msg.usage.input_tokens * 3 + msg.usage.output_tokens * 15) / 1e6
            ledger.record("digest", model=msg.model, prompt_version=version, cost_usd=cost)
            return text
        except Exception as e:
            ledger.record("digest", ok=False, detail=str(e))
    b = data.get("best_clip")
    ledger.record("digest", model="template", cost_usd=0)
    return (f"## {data['published_this_week']} clips, {data['total_views_this_week']:,} views this week\n"
            f"- Best: {b['topic']} ({b['views']:,} views)\n" if b else
            "## No clips published this week\n") +            f"- Spend: ${data['spend_usd_this_week']}\n"            f"- Bucket avg views: {data['bucket_avg_views'] or 'no data'}\n"            f"- Top rejections: {data['top_rejection_reasons'] or 'none'}\n\n"            "**Recommendation:** publish daily; the loops need data."

def send_email(md: str) -> bool:
    key, to = config.get("RESEND_API_KEY"), config.get("DIGEST_EMAIL")
    if not (key and to):
        return False
    try:
        import urllib.request
        req = urllib.request.Request("https://api.resend.com/emails", method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            data=json.dumps({"from": "digest@resend.dev", "to": [to],
                             "subject": "Weekly content digest", "text": md}).encode())
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception as e:
        ledger.record("digest", ok=False, detail=f"email: {e}")
        return False

def run(force=False) -> str | None:
    last = config.get_setting("digest_last_ts", 0) or 0
    if not force and time.time() - float(last) < 7 * 86400 - 3600:
        return None
    md = compose(build_data())
    config.set_setting("digest_latest", {"md": md, "at": datetime.datetime.utcnow().isoformat()})
    config.set_setting("digest_last_ts", time.time())
    emailed = send_email(md)
    print(f"[digest] generated{' + emailed' if emailed else ''}")
    return md
