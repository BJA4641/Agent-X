# Agent-X v5.8.1 — HOTFIX + DESKTOP LAYOUT
Push these ON TOP of Batch 4 (same paths, complete replacements). If you haven't pushed Batch 4's pipeline files yet — your worker still shows 5.7.0 — push BOTH zips; this one supersedes the overlapping files.

## P0 — the pipeline was crashing on every script (your screenshot caught it)
- `creative.write_script` → UnboundLocalError `job_of`: a v5.7.1-era branch did a LOCAL `from ..common import job_of`, which shadows the module import for the whole function. Every normal write crashed → circuit breaker → auto kill switch ("money out, nothing published"). Fixed; the shadowing import is gone and a double-enqueue on that branch is fixed too.
- The one-letter "U" / "C" idea cards: `scout.recent_trends()` returns prompt TEXT, and the topic picker iterated it — character by character. New structured `recent_trend_titles()` + length guards. Junk items already cleared in the live DB.
- Tests still 49/49.

## Desktop layout (the real cause of "mobile-only feel")
`.wrap` capped every page at 1080px, then the dashboard carved 220px + 300px rails out of it — your MAIN column was ~500px on a 1920px monitor. Now:
- Dashboard/Studio/Trends shell widens to 1680px with responsive breakpoints (1500 / 1180 / 860). The right rail drops below content on small screens; pages without a rail (Studio, Trends) reclaim its space automatically.
- Studio board cards flow into 2 columns on wide screens, 1 on narrow.
- Workspace agent feed stops wrapping every two words — its 1fr message column finally has room.
Mobile is untouched (block layout under 860px, same as before).

## After pushing, verify
1. /api/version → web 5.8.1 AND worker 5.8.1 (if worker still says 5.7.0, Railway didn't rebuild — check its deploy log).
2. Studio on your laptop: content should fill the screen, cards in 2 columns.
3. Within ~2 ticks: new idea topics are real sentences, scripts flow past write without circuit-breaker events, and reels reach drafted with video + download.
