"""strategy.py — plans next topics from performance. Claude (live) or rotation (dry-run)."""
import json, re, urllib.request
from . import config, ledger, board, llm

FEEDS = [
    "https://news.google.com/rss/search?q=AI+tools+when:7d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=ChatGPT+OR+Gemini+OR+Claude+feature+when:7d&hl=en-US&gl=US&ceid=US:en",
]

def trends(limit=12, niche=None) -> list:
    """Fresh niche headlines. Prefers LIVE scouted data (Reddit/News/HN/YT via
    scout.py) when the Trend Scout has run in the last 24h; falls back to the
    original RSS pull. Zero keys, zero cost, safe empty list on failure."""
    try:
        from . import scout
        hot = scout.cached_trends(limit=limit, niche=niche)
        if len(hot) >= 3:
            return hot
    except Exception:
        pass
    out = []
    for url in FEEDS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
                xml = r.read().decode("utf-8", "ignore")
            out += re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", xml)[1:]
        except Exception:
            continue
    seen, clean = set(), []
    for t in out:
        t = re.sub(r"\s*-\s*[^-]+$", "", t).strip()  # strip publisher suffix
        if t and t.lower() not in seen and len(t) > 15:
            seen.add(t.lower()); clean.append(t)
    return clean[:limit]

def competitors(limit=8) -> list:
    """Competitor outlier watch via free YouTube channel RSS — zero keys.
    COMPETITOR_CHANNELS=UCxxxx,UCyyyy (channel IDs). Outlier = views >= 2x that feed's median."""
    ids = [c.strip() for c in config.get("COMPETITOR_CHANNELS", "").split(",") if c.strip()]
    out = []
    for cid in ids[:10]:
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
                xml = r.read().decode("utf-8", "ignore")
            entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
            vids = []
            for e in entries:
                t = re.search(r"<title>(.*?)</title>", e)
                v = re.search(r'views="(\d+)"', e)
                if t and v:
                    vids.append((t.group(1), int(v.group(1))))
            if len(vids) < 4:
                continue
            med = sorted(v for _, v in vids)[len(vids) // 2] or 1
            out += [f"{t} ({v:,} views, {v/med:.0f}x their median)" for t, v in vids if v >= 2 * med]
        except Exception:
            continue
    return out[:limit]

_ROTATION = [
    "3 free AI tools that replace paid apps",
    "The AI setting everyone should turn off",
    "How to make ChatGPT remember your style",
    "One prompt that fixes bad AI writing",
    "AI shortcuts hiding in your phone",
    "Turn any PDF into a study coach with AI",
]

def plan(n: int = None, niche: str = None) -> list:
    n = n or config.BATCH_SIZE
    recent = [i["topic"] for i in board.list()][-20:]
    reported = [i for i in board.list("reported")]
    ranked = sorted(reported, key=lambda i: -_views(i))
    winners = [f"{i['topic']} ({_views(i)} views)" for i in ranked[:3]]
    losers = [f"{i['topic']} ({_views(i)} views)" for i in ranked[-3:]] if len(ranked) > 3 else []
    if llm.ready() and ledger.budget_ok(0.01):
        prompt, version = config.load_prompt("strategy_v3")
        prompt = (prompt.replace("{n}", str(n)).replace("{winners}", "; ".join(winners) or "none yet")
                  .replace("{losers}", "; ".join(losers) or "none yet").replace("{trends}", "; ".join(trends(niche=niche)) or "none available").replace("{proven}", "; ".join(competitors()) or "none configured")
                  .replace("{recent}", "; ".join(recent)))
        if niche:
            prompt += ("\nNICHE FOCUS: every idea must serve the '" + str(niche)
                       + "' audience specifically — no generic angles, no AI-tools default.")
        try:
            text, cost, mlabel = llm.chat(prompt, max_tokens=400)
            raw = json.loads(text[text.find("{"): text.rfind("}") + 1])["topics"][:n]
            topics = [t if isinstance(t, dict) else {"topic": t, "bucket": "proven"} for t in raw]
            ledger.record("strategy", model=mlabel, prompt_version=version, cost_usd=cost)
            return topics
        except Exception as e:
            ledger.record("strategy", ok=False, detail=str(e))
    fresh = [t for t in _ROTATION if t not in recent] or _ROTATION
    ledger.record("strategy", model="rotation", cost_usd=0)
    return [{"topic": t, "bucket": "proven"} for t in fresh[:n]]

def _views(item):
    m = item["payload"].get("metrics", {})
    return sum(v.get("views", 0) for v in m.values())
