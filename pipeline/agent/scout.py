"""scout.py — the Trend Scout agent.

Scouts LIVE trending content across platforms for every niche your users
picked in onboarding (plus SCOUT_NICHES from env), scores each item by
heat (engagement x freshness), and writes rows into the `trend_items`
table so the /trends desk and the strategist both read REAL data.

Sources (all free, no keys needed):
  - Reddit        top posts of the day per niche subreddit (upvotes+comments)
  - Google News   fresh headlines per niche query
  - Hacker News   Algolia API (tech niches only — points+comments)
  - YouTube       Data API most-viewed recent videos (ONLY if YOUTUBE_API_KEY set)

Design rules:
  - Never raises out of run(): a dead source is skipped, the rest continue.
  - Zero LLM cost. Pure HTTP + arithmetic.
  - Supabase upsert keyed on url (no duplicates); rows older than 72h pruned.
  - Local JSON fallback when Supabase is not configured (dev machines).
  - maybe_run() guards to one scout pass per SCOUT_INTERVAL_MIN (default 30).
"""
from __future__ import annotations
import json, math, os, re, time, urllib.parse, urllib.request
from . import config, events

UA = {"User-Agent": "Mozilla/5.0 (AgentX-scout/1.0)"}
LOCAL = os.path.join(os.path.dirname(__file__), "..", "data", "trends-local.json")
MAX_NICHES_PER_RUN = 6
KEEP_HOURS = 72

# One entry per onboarding niche slug. query feeds Google News + YouTube search.
NICHE_SOURCES = {
    "ai_tools":      {"subs": ["ChatGPT", "artificial", "OpenAI"],          "query": "AI tools",              "hn": True},
    "fitness":       {"subs": ["Fitness", "bodyweightfitness"],             "query": "fitness workout viral"},
    "finance":       {"subs": ["personalfinance", "Fire"],                  "query": "money side hustle"},
    "cooking":       {"subs": ["Cooking", "MealPrepSunday"],                "query": "easy recipe viral"},
    "skincare":      {"subs": ["SkincareAddiction", "30PlusSkinCare"],      "query": "skincare routine"},
    "gaming":        {"subs": ["gaming", "GameDeals"],                      "query": "gaming news"},
    "real_estate":   {"subs": ["realestateinvesting", "RealEstate"],        "query": "real estate investing"},
    "saas":          {"subs": ["SaaS", "startups", "Entrepreneur"],         "query": "SaaS growth startup", "hn": True},
    "coaching":      {"subs": ["getdisciplined", "selfimprovement"],        "query": "self improvement habits"},
    "travel":        {"subs": ["travel", "TravelHacks"],                    "query": "travel hacks destinations"},
    "fashion":       {"subs": ["femalefashionadvice", "malefashionadvice"], "query": "fashion trends outfit"},
    "parenting":     {"subs": ["Parenting", "Mommit"],                      "query": "parenting hacks"},
    "crypto":        {"subs": ["CryptoCurrency", "Bitcoin"],                "query": "crypto bitcoin news"},
    "music":         {"subs": ["WeAreTheMusicMakers", "musicproduction"],   "query": "music production"},
    "pets":          {"subs": ["Dogtraining", "cats"],                      "query": "pet tips viral"},
    "diy":           {"subs": ["DIY", "HomeImprovement"],                   "query": "DIY home project"},
    "cars":          {"subs": ["cars", "MechanicAdvice"],                   "query": "car maintenance mods"},
    "education":     {"subs": ["GetStudying", "studytips"],                 "query": "study tips exam"},
    "productivity":  {"subs": ["productivity", "Notion"],                   "query": "productivity system Notion"},
    "mental_health": {"subs": ["mentalhealth", "Anxiety"],                  "query": "mental health self care"},
}


# ---------------------------------------------------------------- public api
def maybe_run(interval_min: int = None) -> bool:
    """Run at most once per interval. Called from every orchestrator tick."""
    interval_min = interval_min or int(config.get("SCOUT_INTERVAL_MIN", "30"))
    last = config.get_setting("scout_last_ts") or 0
    try:
        last = float(last if not isinstance(last, dict) else last.get("ts", 0))
    except Exception:
        last = 0
    if time.time() - last < interval_min * 60:
        return False
    run()
    config.set_setting("scout_last_ts", {"ts": time.time()})
    return True


def run(niches: list = None) -> int:
    """One full scout pass across all active niches. Returns rows written."""
    niches = niches or active_niches()
    events.emit("scout", "Scouting " + str(len(niches)) + " niche(s): " + ", ".join(niches)
                + " — Reddit, Google News" + (", YouTube API" if _yt_key() else "")
                + ". Zero token cost.", "info", "scout_start")
    total, top = 0, None
    for niche in niches:
        src = NICHE_SOURCES.get(niche) or {"subs": [], "query": niche.replace("_", " ")}
        rows = []
        for sub in src.get("subs", [])[:3]:
            rows += _reddit(sub, niche)
        rows += _google_news(src["query"], niche)
        if src.get("hn"):
            rows += _hackernews(src["query"], niche)
        rows += _youtube(src["query"], niche)
        rows = _dedupe(rows)
        for r in rows:
            r["heat"] = _heat(r)
        rows.sort(key=lambda r: -r["heat"])
        rows = rows[:25]
        n = _store(rows)
        total += n
        if rows and (top is None or rows[0]["heat"] > top["heat"]):
            top = rows[0]
        events.emit("scout", niche + ": " + str(len(rows)) + " hot items"
                    + (" — top: '" + rows[0]["title"][:70] + "' (heat " + str(rows[0]["heat"]) + ")" if rows else ""),
                    "success" if rows else "warn", "scout_niche")
    _prune()
    if top:
        events.emit("scout", "Scout pass done — " + str(total) + " items on the trends desk. "
                    "Hottest overall: '" + top["title"][:70] + "'.", "success", "scout_done")
    else:
        events.emit("scout", "Scout pass done — sources quiet or rate-limited; will retry next pass.",
                    "warn", "scout_done")
    return total


def active_niches() -> list:
    """env SCOUT_NICHES + every distinct niche your users picked in onboarding."""
    out = [n.strip() for n in config.get("SCOUT_NICHES", "ai_tools").split(",") if n.strip()]
    if config.HAS_SUPABASE:
        try:
            res = _sb().table("profiles").select("niche").not_.is_("niche", "null").execute()
            for row in res.data or []:
                n = (row.get("niche") or "").strip()
                if n and n not in out:
                    out.append(n)
        except Exception:
            pass
        try:  # v1.6: projects table niches too (multi-project accounts)
            res = _sb().table("projects").select("niche").eq("status", "active").execute()
            for row in res.data or []:
                n = (row.get("niche") or "").strip()
                if n and n not in out:
                    out.append(n)
        except Exception:
            pass  # table not migrated yet — fine
    return out[:MAX_NICHES_PER_RUN]


def cached_trends(limit: int = 12, niche: str = None) -> list:
    """Fresh scouted titles for the strategist. Empty list when nothing scouted."""
    try:
        if config.HAS_SUPABASE:
            cutoff = _iso(time.time() - 24 * 3600)
            q = _sb().table("trend_items").select("title,heat,niche").gte("scraped_at", cutoff)
            if niche:
                q = q.eq("niche", niche)
            res = q.order("heat", desc=True).limit(limit).execute()
            return [r["title"] for r in (res.data or [])]
        if os.path.exists(LOCAL):
            rows = json.load(open(LOCAL))
            rows = [r for r in rows if time.time() - r.get("scraped_ts", 0) < 24 * 3600
                    and (not niche or r.get("niche") == niche)]
            rows.sort(key=lambda r: -r.get("heat", 0))
            return [r["title"] for r in rows[:limit]]
    except Exception:
        pass
    return []


# ---------------------------------------------------------------- sources
def _reddit(sub: str, niche: str) -> list:
    url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit=12&raw_json=1"
    data = _get_json(url)
    out = []
    for c in (data or {}).get("data", {}).get("children", []):
        d = c.get("data", {})
        if d.get("stickied") or d.get("over_18"):
            continue
        title = (d.get("title") or "").strip()
        if len(title) < 15:
            continue
        out.append({
            "niche": niche, "platform": "reddit",
            "title": title[:200],
            "url": "https://www.reddit.com" + (d.get("permalink") or ""),
            "author": "r/" + sub,
            "views": int(d.get("ups") or 0),
            "engagement": int(d.get("ups") or 0) + int(d.get("num_comments") or 0),
            "published_ts": float(d.get("created_utc") or time.time()),
        })
    return out


def _google_news(query: str, niche: str) -> list:
    q = urllib.parse.quote(query + " when:2d")
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    xml = _get_text(url)
    out = []
    for item in re.findall(r"<item>(.*?)</item>", xml or "", re.S)[:10]:
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", item)
        l = re.search(r"<link>(.*?)</link>", item)
        p = re.search(r"<pubDate>(.*?)</pubDate>", item)
        if not t:
            continue
        title = re.sub(r"\s*-\s*[^-]+$", "", _unescape(t.group(1))).strip()
        if len(title) < 15:
            continue
        ts = _parse_rfc822(p.group(1)) if p else time.time()
        out.append({"niche": niche, "platform": "news", "title": title[:200],
                    "url": (l.group(1).strip() if l else "#"), "author": "Google News",
                    "views": 0, "engagement": 0, "published_ts": ts})
    return out


def _hackernews(query: str, niche: str) -> list:
    since = int(time.time() - 3 * 86400)
    q = urllib.parse.quote(query)
    url = (f"https://hn.algolia.com/api/v1/search?query={q}&tags=story"
           f"&numericFilters=created_at_i>{since}&hitsPerPage=8")
    data = _get_json(url)
    out = []
    for h in (data or {}).get("hits", []):
        title = (h.get("title") or "").strip()
        if len(title) < 15:
            continue
        out.append({"niche": niche, "platform": "hackernews", "title": title[:200],
                    "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
                    "author": "Hacker News",
                    "views": int(h.get("points") or 0),
                    "engagement": int(h.get("points") or 0) + int(h.get("num_comments") or 0),
                    "published_ts": float(h.get("created_at_i") or time.time())})
    return out


def _youtube(query: str, niche: str) -> list:
    key = _yt_key()
    if not key:
        return []
    week_ago = _iso(time.time() - 7 * 86400) + "Z"
    q = urllib.parse.quote(query)
    surl = ("https://www.googleapis.com/youtube/v3/search?part=snippet&type=video"
            f"&q={q}&order=viewCount&publishedAfter={week_ago}&maxResults=8&key={key}")
    sdata = _get_json(surl)
    ids = [i["id"]["videoId"] for i in (sdata or {}).get("items", []) if i.get("id", {}).get("videoId")]
    if not ids:
        return []
    vurl = ("https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet"
            f"&id={','.join(ids)}&key={key}")
    vdata = _get_json(vurl)
    out = []
    for v in (vdata or {}).get("items", []):
        sn, st = v.get("snippet", {}), v.get("statistics", {})
        title = (sn.get("title") or "").strip()
        if len(title) < 10:
            continue
        views = int(st.get("viewCount") or 0)
        out.append({"niche": niche, "platform": "youtube", "title": title[:200],
                    "url": "https://www.youtube.com/watch?v=" + v["id"],
                    "author": sn.get("channelTitle") or "YouTube",
                    "views": views,
                    "engagement": views + int(st.get("likeCount") or 0) * 20,
                    "published_ts": _parse_iso(sn.get("publishedAt"))})
    return out


def _yt_key():
    return config.get("YOUTUBE_API_KEY") or config.get("YT_API_KEY")


# ---------------------------------------------------------------- scoring/store
def _heat(r: dict) -> int:
    """1-99. Engagement (log scale) + freshness. News has no metrics -> freshness-led."""
    age_h = max(0.0, (time.time() - r.get("published_ts", time.time())) / 3600)
    fresh = max(0.0, (48 - age_h)) / 48 * 42            # 0-42
    eng = math.log10(max(r.get("engagement", 0), 0) + 10) * 13   # ~13-57 for 0..1M
    base = 8 if r["platform"] == "news" else 0           # news floor so it ranks
    return int(max(1, min(99, round(fresh + eng + base))))


def _dedupe(rows: list) -> list:
    seen, out = set(), []
    for r in rows:
        k = r["url"] or r["title"].lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _store(rows: list) -> int:
    if not rows:
        return 0
    if config.HAS_SUPABASE:
        payload = [{
            "tenant_id": config.TENANT_ID, "niche": r["niche"], "platform": r["platform"],
            "title": r["title"], "url": r["url"], "author": r.get("author"),
            "views": r.get("views", 0), "engagement": r.get("engagement", 0),
            "heat": r["heat"], "published_at": _iso(r.get("published_ts", time.time())),
            "scraped_at": _iso(time.time()),
        } for r in rows]
        try:
            _sb().table("trend_items").upsert(payload, on_conflict="url").execute()
            return len(payload)
        except Exception as e:
            events.emit("scout", "trend_items write failed (run db/scout.sql?): " + str(e)[:120],
                        "warn", "scout_db")
            return 0
    # local fallback
    old = json.load(open(LOCAL)) if os.path.exists(LOCAL) else []
    have = {r.get("url") for r in old}
    for r in rows:
        if r["url"] not in have:
            old.append({**r, "scraped_ts": time.time()})
    old = [r for r in old if time.time() - r.get("scraped_ts", 0) < KEEP_HOURS * 3600]
    os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
    json.dump(old, open(LOCAL, "w"), indent=1)
    return len(rows)


def _prune():
    if not config.HAS_SUPABASE:
        return
    try:
        cutoff = _iso(time.time() - KEEP_HOURS * 3600)
        _sb().table("trend_items").delete().lt("scraped_at", cutoff).execute()
    except Exception:
        pass


# ---------------------------------------------------------------- plumbing
def _get_json(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
            return json.load(r)
    except Exception:
        return None


def _get_text(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        return ""


def _unescape(s):
    for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"),
                 ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        s = s.replace(a, b)
    return s


def _parse_rfc822(s):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(s).timestamp()
    except Exception:
        return time.time()


def _parse_iso(s):
    try:
        import datetime
        return datetime.datetime.fromisoformat((s or "").replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time()


def _iso(ts):
    import datetime
    return datetime.datetime.utcfromtimestamp(ts).isoformat()


def _sb():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
