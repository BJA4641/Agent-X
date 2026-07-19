"""scout.py v4.1 — Trend Scout.
Maintains a rotating library of viral HOOK/STRUCTURE patterns that feeds the scriptwriter
and strategist so content matches what's popping THIS week.

Existing trend_items table columns: tenant_id, niche, platform, title, url, author,
views, engagement, heat, published_at, scraped_at.

We seed it with "trend pattern" rows (platform='pattern') describing the ANGLE, TONE,
AUDIO, and PACING of currently-working content. Scriptwriter reads the top N "hottest"
patterns before writing any script. We CLONE THE ANGLE — never repost content.
"""
from . import config, events
import time

# Curated rotating viral-pattern library (last refreshed July 2026).
# Each entry is an ANGLE/STRUCTURE — not actual content.
_VIRAL_PATTERNS = [
  {"niche":"ai_tools","title":"Pattern-interrupt 2-word hook","url":"pattern:pattern_interrupt","author":"curated",
   "views":0,"engagement":0,"heat":98,
   "angle":"pattern_interrupt","hooks":"stop scrolling. | wait until end. | don't scroll. | hold on.",
   "tone":"deadpan, almost whisper","pacing_bpm":120,"beats":6,
   "audio":"rising tension drone + boom SFX on hook cut","energy":"slow burn then fast cuts"},
  {"niche":"ai_tools","title":"Specific number listicle","url":"pattern:specific_number","author":"curated",
   "views":0,"engagement":0,"heat":92,
   "angle":"specific_number","hooks":"3 apps that replaced my job. | the $0 tool that beats ChatGPT. | 7 seconds = done.",
   "tone":"confident, matter-of-fact","pacing_bpm":130,"beats":6,
   "audio":"lofi tech bed with tick SFX per count","energy":"snappy listicle zoom-ins"},
  {"niche":"ai_tools","title":"Contrarian truth bomb","url":"pattern:contrarian","author":"curated",
   "views":0,"engagement":0,"heat":87,
   "angle":"contrarian_truth","hooks":"most AI tools are useless. | you don't need a course. | the guru lied.",
   "tone":"blunt, almost annoyed","pacing_bpm":125,"beats":6,
   "audio":"ominous sub bass + whip pans","energy":"aggressive fast cuts"},
  {"niche":"general","title":"Secret reveal","url":"pattern:secret","author":"curated",
   "views":0,"engagement":0,"heat":85,
   "angle":"secret_reveal","hooks":"nobody talks about this. | they hid this button. | the free version is better.",
   "tone":"conspiratorial, quiet","pacing_bpm":118,"beats":6,
   "audio":"mystery pad + riser into beat drop","energy":"push-in zooms, UI closeups"},
  {"niche":"general","title":"Relatable pain opener","url":"pattern:relatable","author":"curated",
   "views":0,"engagement":0,"heat":80,
   "angle":"relatable_pain","hooks":"I wasted 3 years on this. | this used to take me 4 hours. | I quit my job because.",
   "tone":"genuine, vulnerable","pacing_bpm":115,"beats":7,
   "audio":"emotional soft pad + soft sub","energy":"slow push-in, B-roll"},
  {"niche":"general","title":"Demo showcase fast cuts","url":"pattern:demo","author":"curated",
   "views":0,"engagement":0,"heat":95,
   "angle":"demo_showcase","hooks":"watch this. | just press this. | I can't believe this works.",
   "tone":"excited, kid-in-candy-store","pacing_bpm":135,"beats":5,
   "audio":"hyperpop bed with pop SFX per click","energy":"screen-record zoom-ins, punch cuts"},
  {"niche":"general","title":"Mistake warning","url":"pattern:warning","author":"curated",
   "views":0,"engagement":0,"heat":82,
   "angle":"mistake_warning","hooks":"you're doing it wrong. | stop doing this. | delete this now.",
   "tone":"urgent, direct","pacing_bpm":128,"beats":6,
   "audio":"alert beep + tense drone","energy":"red X overlays, flash-red transitions"},
  {"niche":"money","title":"Result-first proof","url":"pattern:result","author":"curated",
   "views":0,"engagement":0,"heat":90,
   "angle":"result_first","hooks":"$400/day from this. | 10k followers in 12 days. | I built this in 11 minutes.",
   "tone":"calm, proof-heavy","pacing_bpm":122,"beats":6,
   "audio":"cash SFX + lofi bed","energy":"screen-rec proof then how-to"},
]


def _sb():
    from supabase import create_client
    return create_client(config.get("SUPABASE_URL"), config.supabase_service_key())


def ensure_seeded():
    """Idempotently seed the trend library if empty."""
    if not config.HAS_SUPABASE: return 0
    try:
        sb = _sb()
        existing = (sb.table("trend_items").select("id")
                    .eq("tenant_id", config.TENANT_ID)
                    .eq("platform", "pattern").limit(1).execute().data)
        if existing: return 0
        rows = []
        for p in _VIRAL_PATTERNS:
            rows.append({
                "tenant_id": config.TENANT_ID,
                "niche": p["niche"], "platform": "pattern",
                "title": p["title"], "url": p["url"], "author": p["author"],
                "views": 0, "engagement": 0, "heat": p["heat"],
                "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        for i in range(0, len(rows), 20):
            sb.table("trend_items").insert(rows[i:i+20]).execute()
        # Also remember payload in a simple JSON side-channel via memory? No — we
        # keep the detailed fields in code so we don't need to re-DB-schema them.
        events.emit("scout", f"Seeded {len(rows)} viral trend patterns.", "info", "scout_seed")
        return len(rows)
    except Exception as e:
        print(f"[scout] seed failed: {e}")
        return 0


def recent_trends(limit: int = 4) -> str:
    """Return a formatted bullet-block of hot patterns for prompt injection."""
    patterns = _VIRAL_PATTERNS[:limit]
    # In the future, live-scraped trends go here. For now we use curated patterns sorted by heat.
    try:
        ordered = sorted(_VIRAL_PATTERNS, key=lambda p: -p["heat"])
        patterns = ordered[:limit]
    except Exception:
        pass
    out = ["CURRENT VIRAL PATTERNS (clone the ANGLE/STRUCTURE — never the actual words, never repost):"]
    for p in patterns:
        out.append(
          f"- Pattern: {p['angle']} | Hooks: {p['hooks'][:80]} "
          f"| Tone: {p['tone']} | Pacing: {p['beats']} beats @ {p['pacing_bpm']}bpm | Audio: {p['audio']}"
        )
    return "\n".join(out)


def run() -> int:
    return ensure_seeded()
