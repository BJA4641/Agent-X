# Agent-X v5.8.0 — BATCH 4 "SHIP IT"
Drag every file into GitHub web UI at the SAME paths (complete replacements). Railway + Vercel redeploy automatically. Verify: /api/version → web 5.8.0 + worker 5.8.0.

## What's in the box
1. **RENDER DELIVERY (the big one)** — rendered reels now upload to Supabase Storage (`renders` bucket, already created live). Studio plays the video + "⬇ Download reel" link. Before this, finished mp4s were trapped on Railway's ephemeral disk — unplayable, undownloadable, wiped on every redeploy. This is what makes manual posting physically possible.
2. **MULTI-ACCOUNT FIX** — portfolio.tick looped on the FIRST active account only (old single-account mandate). Now every active account gets its own daily reel spawn. puppy.parent starts producing.
3. **CAROUSELS** — 3/week per account (Mon/Wed/Fri GMT by default; `config.carousels_per_week` 1–7). Chain: plan → write (1 LLM call, strict JSON, budget-gated) → render 5 slides (1080×1350, brand-style bg + text card) → upload → `approved` in Studio with slide strip, per-slide open/save, caption + best-time windows. ~$0.10–0.25 each, ~$0 in econ mode.
4. **CLONE-A-POST** — account page → Overview → "🎯 Clone a trending post". Paste URL + describe the post + pick reel/carousel → HIGH-priority account-bound item + job (inserted atomically — bare board ideas are decoration, nothing consumes them). Honest limits in the UI: IG login-walls URLs, so your description is the brief; agents clone the ANGLE originally, never repost.
5. **GEO WIRING** — captions now carry `post_windows` from account `target_geos` (AE/US/CA/LB set live earlier) + audience line in carousel prompts. Reel/carousel cards show best posting times.
6. **ECON MODE** — Studio toggle (green 💚). Visuals skip the paid image branch → Gemini free tier → procedural. Honest scope: **visuals-only in v1**; LLM free-provider preference lands in 5.8.1.
7. **BONUS BUG KILL** — new contract test exposed that `brain.captions()` has been throwing TypeError on EVERY call since v1.6 (bad kwarg), silently swallowed → platform captions were always empty. Fixed + account-niche aware now. Tests: 49/49.

## Honest scope notes
- Carousel v1 skips the risk/monetize chain (reels keep it) — joins in a later batch.
- Clone doesn't auto-fetch IG URLs (login-walled; scraping risks accounts). Screenshot-vision intake = v2.
- Stories deferred until ~1k followers (stories only reach existing followers).
- Storage: Supabase free tier = 1 GB ≈ 60–100 reels. Cleanup policy comes in a later batch; delete old files in Storage → renders if it fills.

## First carousel
Today is Thu — with the default Mon/Wed/Fri schedule, the first carousels queue **Friday (GMT)** for both accounts. Force one sooner: account config `{"carousels_per_week": 7}`.
