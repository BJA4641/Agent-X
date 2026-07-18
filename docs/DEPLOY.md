# Deploy guide — in this exact order

## 0. GitHub (do this first, before anything else)
```bash
cd buildalong && git init && git add -A && git commit -m "v0.2 monorepo"
```
Create a private repo on github.com, then `git remote add origin ... && git push -u origin main`.
This repo is now the source of truth — never again "the zip on my laptop".

## 0. Try it in 5 minutes (zero keys, before any deploy)
```
cd pipeline && pip install -r requirements.txt
python cli.py demo "Your first topic here"
```
One finished vertical video lands in `pipeline/output/` — real free voice (edge-tts), one of 8 art styles, background music bed mixed under the narration. Judge it like a viewer. Add `ANTHROPIC_API_KEY` and the script gets smart; add `GEMINI_API_KEY` and the visuals go AI-generated. Everything after this section is about putting it on autopilot.

## 1. Supabase (database + auth + media storage) — one project serves both apps
1. supabase.com → New project (pick a region near you).
2. SQL editor → paste **db/schema.sql** → Run.
3. Storage → New bucket → name `media` → **Public** (Instagram needs public video URLs).
4. Storage -> New bucket -> name `proofs`, **Public OFF** (private). Course verification screenshots are stored here; the app reads them with the service key only.
4. Auth → Providers → Email → for early testing, turn OFF "Confirm email".
5. Copy from Settings → API:
   - Project URL → `NEXT_PUBLIC_SUPABASE_URL` (web) and `SUPABASE_URL` (pipeline)
   - anon key → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (web only)
   - service_role key → `SUPABASE_SERVICE_ROLE_KEY` (web server) and `SUPABASE_SERVICE_KEY` (pipeline). NEVER expose this in the browser.

## 2. Web → Vercel
1. vercel.com → Import the GitHub repo → set **Root Directory = `web`**.
2. Add every var from `web/.env.example` in Project → Settings → Environment Variables.
3. Deploy. Set `NEXT_PUBLIC_SITE_URL` to the final URL and redeploy.
Works immediately with only the Supabase vars: landing, waitlist, signup, the free Instagram track with saved progress.

## 3. Payments (only when a paid track opens — not needed for launch)
- **If Stripe supports your country:** Stripe → 2 one-time $200 Prices → put ids in `STRIPE_PRICE_YT` / `STRIPE_PRICE_ECOM`; add secret key; add a webhook endpoint `https://YOURSITE/api/stripe-webhook` for `checkout.session.completed`, copy its signing secret.
- **If it doesn't (much of MENA):** use Paddle or Lemon Squeezy as merchant of record — swap `app/api/checkout` + webhook for their equivalents (~1 hour of work). The rest of the app doesn't change. Decide by your incorporation country.

## 4. Pipeline worker → Railway (or any always-on box)
Vercel/Cloudflare can't run this (long ffmpeg jobs). Railway is the least-friction host:
1. railway.app → New project → Deploy from GitHub repo → set **Dockerfile path = `pipeline/Dockerfile`**, root = repo root.
2. Add env vars from `pipeline/.env.example` (start with just `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` + `GEMINI_API_KEY` + `ANTHROPIC_API_KEY`).
3. It ticks every 30 min. Approve drafts with `python cli.py approve <id>` locally against the same Supabase board (or from the future dashboard).
Alternative: run it on your own computer first — `python cli.py loop` — that's a legitimate Phase-1 deployment.

## 4a. Optional worker upgrades (no new accounts)
`COMMUNITY_AUTOREPLY` — after Meta approval the worker drafts replies to every new comment (visible in /studio with copy buttons). Set to `1` to let it reply automatically.
`RESEND_API_KEY` + `DIGEST_EMAIL` — free resend.com key = weekly digest emailed to you; without it the digest still renders in /studio every week.
`COMPETITOR_CHANNELS` — paste 3-5 YouTube channel IDs from your niche and Strategy will detect their outlier videos (views far above their own median) and plan proven-demand angles from them. Zero keys, uses public RSS.

## 4b. Your control room
After web + Supabase are live: sign up on your own site with the email you put in `ADMIN_EMAILS`, then open **/studio** — board, video previews, approve/reject-with-reason, spend, kill switch. This replaces the CLI for daily use.

## 5. Platform accounts (start the clock, post manually meanwhile)
- Instagram: create a **Business/Creator** account manually → developers.facebook.com → app → Instagram Graph API → submit App Review (2–4 weeks). **You can and should post manually from day one** — the API is only for automation.
- YouTube: channel + Google Cloud project → YouTube Data API v3 → OAuth client → token json.

## Env var map (who needs what)
| Var | web (Vercel) | pipeline (Railway) |
|---|---|---|
| NEXT_PUBLIC_SUPABASE_URL / SUPABASE_URL | ✅ | ✅ |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | ✅ | — |
| SUPABASE_SERVICE_ROLE_KEY / SUPABASE_SERVICE_KEY | ✅ (server) | ✅ |
| STRIPE_* | ✅ | — |
| ADMIN_EMAILS (unlocks /studio), TENANT_ID | ✅ | — / ✅ |
| ANTHROPIC_API_KEY, GEMINI_API_KEY, ELEVENLABS_API_KEY | — | ✅ |
| IG_*, YT_* | — | ✅ |
| DAILY_BUDGET_USD, KILL_SWITCH, TENANT_ID | — | ✅ |

### Music
Drop royalty-free tracks (mp3/wav) into `pipeline/assets/music/` (or set `MUSIC_DIR`) — good free sources: Pixabay Music, YouTube Audio Library, Incompetech. Track choice is deterministic per video. No tracks present -> a subtle synth ambient bed is used (`MUSIC_SYNTH=0` disables). `MUSIC_VOLUME` (default 0.12) sets the duck level under the voice. During your manual-posting weeks, adding a *trending* sound natively in the IG app on top beats anything automatable — do that for your biggest swings.

### Visual style
`STYLE=auto` (default) rotates 8 art directions deterministically per video: editorial, neon, clay, collage, cinematic, blueprint, retro, glass. Pin one account-wide with `STYLE=neon`, or per-video from the board payload (`{"style": "blueprint"}`).
