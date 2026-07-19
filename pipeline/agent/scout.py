"""scout.py v4.3 — the Trend Scout agent (full live scraper + viral pattern library).

Scouts LIVE trending content across platforms for every niche your users
picked in onboarding (plus SCOUT_NICHES from env), scores each item by
heat (engagement x freshness), and writes rows into the `trend_items`
table so the /trends desk and the strategist both read REAL data.

Sources (all free, no keys needed):
  - Reddit        top posts of the day per niche subreddit (upvotes+comments)
  - Google News   fresh headlines per niche query
  - Hacker News   Algolia API (tech niches only — points+comments)
  - YouTube       Data API most-viewed recent videos (ONLY if YOUTUBE_API_KEY set)

PLUS a curated VIRAL PATTERN library (8 proven hook/structure patterns that are
currently working). These seed into trend_items as platform='pattern' rows so
the strategist and brain always have structural inspiration — even when the live
sources are quiet. Clone the ANGLE, never the words.

Design rules:
  - Never raises out of run(): a dead source is skipped, the rest continue.
  - Zero LLM cost. Pure HTTP + arithmetic.
  - Supabase upsert keyed on url (no duplicates); rows older than 72h pruned.
  - Local JSON fallback when Supabase is not configured (dev machines).
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
    "cats":          {"subs": ["cats", "CatAdvice"],                        "query": "cat facts viral",       "hn": False},
    "pets":          {"subs": ["Dogtraining", "cats", "pets"],              "query": "pet tips viral",        "hn": False},
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
    "diy":           {"subs": ["DIY", "HomeImprovement"],                   "query": "DIY home project"},
    "cars":          {"subs": ["cars", "MechanicAdvice"],                   "query": "car maintenance mods"},
    "education":     {"subs": ["GetStudying", "studytips"],                 "query": "study tips exam"},
    "productivity":  {"subs": ["productivity", "Notion"],                   "query": "productivity system Notion"},
    "mental_health": {"subs": ["mentalhealth", "Anxiety"],                  "query": "mental health self care"},
}

# Curated rotating viral PATTERN library (last refreshed July 2026).
# These describe STRUCTURE/ANGLE — not actual content. They seed into trend_items
# as platform='pattern' rows so the writer can match the angle of what's working.
_VIRAL_PATTERNS = [
  {"title":"Pattern-interrupt 2-word hook","url":"pattern:pattern_interrupt",
   "angle":"pattern_interrupt","hooks":"stop scrolling. | wait until end. | don't scroll. | hold on.",
   "tone":"deadpan, almost whisper","pacing_bpm":120,"beats":6,"heat":98,
   "audio":"rising tension drone + boom SFX on hook cut","energy":"slow burn then fast cuts"},
  {"title":"Specific number listicle","url":"pattern:specific_number",
   "angle":"specific_number","hooks":"3 apps that replaced my job. | the $0 tool that beats ChatGPT. | 7 seconds = done.",
   "tone":"confident, matter-of-fact","pacing_bpm":130,"beats":6,"heat":92,
   "audio":"lofi tech bed with tick SFX per count","energy":"snappy listicle zoom-ins"},
  {"title":"Contrarian truth bomb","url":"pattern:contrarian_truth",
   "angle":"contrarian_truth","hooks":"most AI tools are useless. | you don't need a course. | the guru lied.",
   "tone":"blunt, almost annoyed","pacing_bpm":125,"beats":6,"heat":87,
   "audio":"ominous sub bass + whip pans","energy":"aggressive fast cuts"},
  {"title":"Secret reveal","url":"pattern:secret_reveal",
   "angle":"secret_reveal","hooks":"nobody talks about this. | they hid this button. | the free version is better.",
   "tone":"conspiratorial, quiet","pacing_bpm":118,"beats":6,"heat":85,
   "audio":"mystery pad + riser into beat drop","energy":"push-in zooms, UI closeups"},
  {"title":"Relatable pain opener","url":"pattern:relatable_pain",
   "angle":"relatable_pain","hooks":"I wasted 3 years on this. | this used to take me 4 hours. | I quit my job because.",
   "tone":"genuine, vulnerable","pacing_bpm":115,"beats":7,"heat":80,
   "audio":"emotional soft pad + soft sub","energy":"slow push-in, B-roll"},
  {"title":"Demo showcase fast cuts","url":"pattern:demo_showcase",
   "angle":"demo_showcase","hooks":"watch this. | just press this. | I can't believe this works.",
   "tone":"excited, kid-in-candy-store","pacing_bpm":135,"beats":5,"heat":95,
   "audio":"hyperpop bed with pop SFX per click","energy":"screen-record zoom-ins, punch cuts"},
  {"title":"Mistake warning","url":"pattern:mistake_warning",
   "angle":"mistake_warning","hooks":"you're doing it wrong. | stop doing this. | delete this now.",
   "tone":"urgent, direct","pacing_bpm":128,"beats":6,"heat":82,
   "audio":"alert beep + tense drone","energy":"red X overlays, flash-red transitions"},
  {"title":"Result-first proof","url":"pattern:result_first",
   "angle":"result_first","hooks":"$400/day from this. | 10k followers in 12 days. | I built this in 11 minutes.",
   "tone":"calm, proof-heavy","pacing_bpm":122,"beats":6,"heat":90,
   "audio":"cash SFX + lofi bed","energy":"screen-rec proof then how-to"},
]


# ---------------------------------------------------------------- public api
def ensure_seeded() -> int:
    """Idempotently seed the viral pattern library if empty. Safe to call every tick."""
    try:
        if config.HAS_SUPABASE:
            sb = _sb()
            existing = (sb.table("trend_items").select("id")
                        .eq("tenant_id", config.TENANT_ID)
                        .eq("platform", "pattern").limit(1).execute().data)
            if existing:
                return 0
            rows = []
            for p in _VIRAL_PATTERNS:
                rows.append({
                    "tenant_id": config.TENANT_ID,
                    "niche": p.get("niche", "general"), "platform": "pattern",
                    "title": p["title"], "url": p["url"], "author": "curated",
                    "views": 0, "engagement": 0, "heat": p["heat"],
                    "published_at": _iso(time.time()),
                    "scraped_at": _iso(time.time()),
                })
            for i in range(0, len(rows), 20):
                sb.table("trend_items").insert(rows[i:i+20]).execute()
            events.emit("scout", f"Seeded {len(rows)} viral trend patterns (pattern_interrupt, specific_number, etc.).",
                        "info", "scout_seed")
            return len(rows)
    except Exception as e:
        print(f"[scout] seed failed: {e}")
    return 0


def recent_trends(limit: int = 5) -> str:
    """Return a formatted bullet-block of hot patterns/titles for prompt injection.

    Always returns something (curated patterns as fallback) so the brain/strategist
    never prompts with empty trend context.
    """
    out_lines = ["CURRENT VIRAL PATTERNS (clone the ANGLE/STRUCTURE — never the actual words, never repost):"]
    # Curated viral patterns (always included, sorted by heat)
    ordered = sorted(_VIRAL_PATTERNS, key=lambda p: -p.get("heat", 0))
    shown = 0
    for p in ordered[:limit]:
        out_lines.append(
            f"- Pattern: {p['angle']} | Hooks: {p['hooks'][:80]} "
            f"| Tone: {p['tone']} | Pacing: {p['beats']} beats @ {p['pacing_bpm']}bpm | Audio: {p['audio']}"
        )
        shown += 1

    # Append 2-3 fresh real-trend titles if available (client-side sorted so we
    # never rely on Supabase's .order() which has been flaky)
    try:
        fresh = _fetch_recent_titles(limit=3)
        if fresh:
            out_lines.append("\nRECENT HOT TOPICS in this niche (pull from these angles):")
            for t in fresh:
                out_lines.append(f"- {t[:100]}")
    except Exception:
        pass

    return "\n".join(out_lines)


def _fetch_recent_titles(limit: int = 3) -> list:
    """Pull recent trend titles from Supabase, sorted client-side by heat (desc)."""
    out = []
    if config.HAS_SUPABASE:
        try:
            cutoff = _iso(time.time() - 24 * 3600)
            # NOTE: we do NOT use .order("heat", desc=True) — the Supabase-py client
            # has flaky support on some versions. Pull rows then sort in Python.
            res = (_sb().table("trend_items")
                   .select("title,heat,scraped_at")
                   .neq("platform", "pattern")
                   .gte("scraped_at", cutoff)
                   .limit(100).execute())
            rows = [r for r in (res.data or []) if r.get("title")]
            rows.sort(key=lambda r: -(r.get("heat") or 0))
            out = [r["title"] for r in rows[:limit]]
        except Exception:
            out = []
    if not out and os.path.exists(LOCAL):
        try:
            rows = json.load(open(LOCAL))
            rows = [r for r in rows if time.time() - r.get("scraped_ts", 0) < 24 * 3600
                    and r.get("platform") != "pattern"]
            rows.sort(key=lambda r: -(r.get("heat") or 0))
            out = [r["title"] for r in rows[:limit]]
        except Exception:
            pass
    return out


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
    """One full scout pass across all active niches + seed viral patterns. Returns rows written."""
    # Always make sure curated patterns are seeded (cheap, idempotent)
    seeded = ensure_seeded()

    niches = niches or active_niches()
    events.emit("scout", "Scouting " + str(len(niches)) + " niche(s): " + ", ".join(niches)
                + " — Reddit, Google News" + (", YouTube API" if _yt_key() else "")
                + ". Zero token cost.", "info", "scout_start")
    total, top = seeded, None
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
        events.emit("scout", "Scout pass done — sources quiet or rate-limited; curated pattern library always available.",
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
        try:
            res = _sb().table("projects").select("niche").eq("status", "active").execute()
            for row in res.data or []:
                n = (row.get("niche") or "").strip()
                if n and n not in out:
                    out.append(n)
        except Exception:
            pass
    return out[:MAX_NICHES_PER_RUN]


def cached_trends(limit: int = 12, niche: str = None) -> list:
    """Fresh scouted titles for the strategist. Empty list when nothing scouted."""
    try:
        if config.HAS_SUPABASE:
            cutoff = _iso(time.time() - 24 * 3600)
            q = (_sb().table("trend_items").select("title,heat,niche")
                 .neq("platform", "pattern").gte("scraped_at", cutoff))
            if niche:
                q = q.eq("niche", niche)
            # Client-side sort — avoids Supabase .order() flakiness
            res = q.limit(200).execute()
            rows = [r for r in (res.data or []) if r.get("title")]
            rows.sort(key=lambda r: -(r.get("heat") or 0))
            return [r["title"] for r in rows[:limit]]
        if os.path.exists(LOCAL):
            rows = json.load(open(LOCAL))
            rows = [r for r in rows if time.time() - r.get("scraped_ts", 0) < 24 * 3600
                    and (not niche or r.get("niche") == niche)
                    and r.get("platform") != "pattern"]
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
    fresh = max(0.0, (48 - age_h)) / 48 * 42
    eng = math.log10(max(r.get("engagement", 0), 0) + 10) * 13
    base = 8 if r["platform"] == "news" else 0
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
            events.emit("scout", "trend_items write failed: " + str(e)[:120],
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
