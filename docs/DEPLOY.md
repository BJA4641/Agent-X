# Agent-X — Deployment Guide (current, v5.9.x)

> Replaces all `DEPLOY-v5.*-STEPS.txt` files in the repo root — those are
> historical and can be deleted.

## Architecture
- **Web** — Next.js 14 in `web/`, deployed on **Vercel** (project `agent-x`,
  live at agent-x-two.vercel.app). Talks to Supabase only.
- **Worker** — Python in `pipeline/`, deployed on **Railway** via
  `pipeline/Dockerfile` (512MB). Entrypoint: `python cli.py worker`.
  Talks to Supabase only. **Vercel and Railway never talk to each other.**
- **Database** — Supabase project `qrzwoumhfxdwozpasxsn`. Canonical structure:
  `db/schema.sql` (live snapshot). RLS enabled on all tables; worker + web API
  use the service-role key; browser uses the anon key + per-user policies.

## How to deploy (web-UI workflow)
1. Upload changed files to `github.com/BJA4641/Agent-X` main branch
   (drag-and-drop in the GitHub web UI keeps paths).
2. **Vercel** auto-redeploys on push. Verify: Vercel dashboard → latest
   deployment READY, then hard-refresh the site.
3. **Railway** auto-redeploys on push. Verify: Railway → active deployment
   logs → boot line prints the worker version (authoritative source).
4. **DB migrations**: run new SQL in Supabase SQL editor, then regenerate
   `db/schema.sql` so the canonical file never drifts again.

## How to verify the worker is alive
- Supabase SQL editor:
  `select worker_id, version, to_timestamp(last_heartbeat_at) from worker_health;`
  Fresh = heartbeat under 120s old.
- Or the LIVE BUILD banner on the site (green = web + worker agree and beating).

## Env vars (worker, set in Railway)
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY` (+ optional provider keys probed on boot by the Providers
department). Web (Vercel): `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, Stripe keys.
