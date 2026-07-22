# Skill: Trend Scouting & Validation

## Sources (free + legal only)
YouTube channel RSS, Google News RSS, Reddit search JSON, Hacker News Algolia.
Instagram/TikTok have no legal public trend API — topics transfer across
platforms, so validate on the sources above and post natively.

## What counts as a trend signal
- Same subject appearing in ≥2 independent sources within 72h
- A competitor video whose view count is ≥3x that channel's median
- A recurring question phrasing in Reddit titles (people literally asking)

## Output discipline
A trend entry = {title, source, niche_fit(0-1), why_now}. Titles must be
full sentences (≥8 words), never fragments or single words. Anything
shorter than 8 characters is noise — drop it.

## Anti-noise rules
- Ignore engagement-bait ("you won't believe") source titles; extract the
  underlying subject instead.
- Never mark a trend niche_fit>0.5 unless a niche keyword appears in it or
  it maps to a known audience problem for that niche.
