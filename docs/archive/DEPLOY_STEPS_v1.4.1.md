# Agent-X v1.4.1 — Deploy Steps (FIXED version — builds clean)

I found the Vercel build failure you hit: one TypeScript error inside
`web/app/api/wallet/topup/route.ts` — it was selecting only `balance_usd` from the
wallet but then trying to read `lifetime_topup`. That broke Vercel's type check
(the "2" error count in your screenshot was this). This build now passes
`next build` locally with zero errors.

I also fixed the 5 other issues that were on the list, all inside this zip:
1. ✅ Wallet topup TS error (the Vercel red 2)
2. ✅ Trends page HTML entities (`&amp;` / `&quot;`) now decoded correctly
3. ✅ Dashboard layout now auto-redirects new users to /onboarding and gracefully
   skips the redirect if the `profiles` table hasn't been created yet (so the
   site won't crash before you run the SQL)
4. ✅ Pipeline `config.py` accepts BOTH `SUPABASE_SERVICE_KEY` and
   `SUPABASE_SERVICE_ROLE_KEY` — Railway + Vercel can use whichever name you set
5. ✅ Pipeline `Dockerfile` already had `ffmpeg` + `fonts-dejavu-core` installed
6. ✅ Landing page + header rebranded from "BuildAlong" to "Agent-X", with a clear
   "6 ways you actually get paid" section
7. ✅ Tracks expanded to 6: Instagram, YouTube, TikTok, Affiliate, Ecommerce
   store, Digital products — each with a realistic income-layer label
8. ✅ SQL now also creates the 3 storage buckets (media/proofs/agent-avatars) and
   the right RLS policies, so you don't have to click them in the dashboard
9. ✅ Dashboard shows income layer per track and enforces "one track at a time"

---

## STEP 1 — Run the SQL (safe, will NOT destroy your existing data)

1. Open Supabase → SQL Editor → **New query**.
2. Open the file `db/setup_v1.4.sql` from this zip, copy ALL of it, paste into
   the SQL editor, and click **Run**.
3. You will see a result row at the end saying `setup complete`. That means it
   worked.

**Why it is safe to run on your live DB:**
- Every table is created with `CREATE TABLE IF NOT EXISTS` — so your existing
  `board_items`, `run_ledger`, `performance`, `entitlements`, `task_progress`,
  `waitlist`, `settings` tables are **not touched**.
- Every column addition uses `ADD COLUMN IF NOT EXISTS` (there are no drops,
  no deletes, no alters that change types).
- Every RLS policy uses `DROP POLICY IF EXISTS ...; CREATE POLICY ...` so
  re-running the file is harmless.
- The extension `pgcrypto` uses `CREATE EXTENSION IF NOT EXISTS` — already
  installed on every Supabase project.
- The seed data (20 niches) uses `ON CONFLICT DO NOTHING` — no duplicates.

What the SQL adds (new tables only):
- `profiles` + auto-create trigger on new signups
- `user_connections` (encrypted OAuth tokens)
- `brand_profiles`
- `wallets` + `wallet_transactions`
- `agent_events` (Slack-style feed)
- `niches` (20 pre-loaded)
- 3 storage buckets: `media`, `proofs`, `agent-avatars` with correct policies
- Helper functions `encrypt_token` / `decrypt_token` using AES-256

If you get ANY error, copy it exactly and send it to me. Do NOT proceed to the
file upload until the SQL runs without error.

## STEP 2 — Environment variables (Vercel + Railway)

### Vercel (the website)
Go to Vercel → agent-x → Settings → Environment Variables. Make sure these are
set for **Production** (and Preview for testing):

```
NEXT_PUBLIC_SUPABASE_URL        = https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY   = ey...                       (anon/public key)
SUPABASE_SERVICE_ROLE_KEY       = ey...service_role...        (service role, SECRET)
NEXT_PUBLIC_SITE_URL            = https://your-domain.com     (or the *.vercel.app one)
ADMIN_EMAILS                    = your@email.com
# Optional (if left blank wallet runs in free demo mode):
STRIPE_SECRET_KEY               = sk_live_...
STRIPE_WEBHOOK_SECRET           = whsec_...
# Optional (for the admin Trends desk):
COMPETITOR_CHANNELS             = UCxxx,UCyyy
```

### Railway (the Python video pipeline)
In Railway → your pipeline service → Variables:

```
SUPABASE_URL                    = https://xxxx.supabase.co
SUPABASE_SERVICE_KEY            = ey...service_role...
# (SUPABASE_SERVICE_ROLE_KEY is also accepted now — set either one)
ANTHROPIC_API_KEY               = sk-ant-...
GEMINI_API_KEY                  = AI...
DAILY_BUDGET_USD                = 1.50
```

(IG/YT/ElevenLabs keys are optional — the pipeline gracefully falls back to
dry-run if they are missing.)

## STEP 3 — Upload the files to GitHub

Replace/add the following files in your repo (`BJA4641/Agent-X`). If you are
using the GitHub web UI, you can drag-and-drop whole folders. Make sure the
paths match exactly:

### Files to REPLACE (overwrite the old ones)
```
db/schema.sql                                       ← keep old schema if you want, but setup_v1.4.sql is now the canonical one
db/setup_v1.4.sql                                   ← ADD this new file
web/app/page.tsx                                    ← replace (rebranded landing)
web/app/dashboard/page.tsx                          ← replace (income tracks)
web/app/dashboard/layout.tsx                        ← replace (onboarding redirect)
web/app/dashboard/settings/page.tsx                 ← replace (ChannelConnections added)
web/app/trends/page.tsx                             ← replace (entity decode fix)
web/components/Header.tsx                           ← replace (Agent-X logo)
web/components/Sidebar.tsx                          ← replace if you have old version
web/components/ChannelConnections.tsx               ← replace (fixes stuck "Loading...")
pipeline/Dockerfile                                 ← already had ffmpeg+fonts, kept
pipeline/agent/config.py                            ← replace (accepts both env names)
pipeline/.env.example                               ← replace
```

### Files to ADD (new files)
```
web/app/onboarding/page.tsx                         ← new (niche picker)
web/app/wallet/page.tsx                             ← new
web/app/workspace/page.tsx                          ← new (Slack agent feed)
web/app/clone/page.tsx                              ← new
web/app/api/connections/route.ts                    ← new
web/app/api/me/profile/route.ts                     ← new
web/app/api/wallet/route.ts                         ← new
web/app/api/wallet/topup/route.ts                   ← new (TS bug FIXED)
web/app/api/workspace/events/route.ts               ← new
web/lib/tracks.ts                                   ← replace (6 income tracks)
pipeline/agent/brand.py                             ← already in FINAL
pipeline/agent/qa.py
pipeline/agent/planner.py
pipeline/agent/connections.py
prompts/brand_v1.md
prompts/qa_v1.md
```

**Do not DELETE anything else.** Your old Studio, trends, login, proof pages are
still there and still work.

The easiest web-UI way:
1. Open https://github.com/BJA4641/Agent-X
2. Open the `web` folder, then `app`, then click **Add file → Upload files**
3. Drag the subfolders from the unzipped `web/app/` folder in: `onboarding/`,
   `wallet/`, `workspace/`, `clone/`, and the updated `page.tsx`, `dashboard/`
   files.
4. Repeat for `web/components/`, `web/lib/`, `web/app/api/`, `db/`, `pipeline/`,
   `prompts/`.
5. Scroll to the bottom, commit message: `v1.4.1: fix build + rebrand Agent-X + 6 income tracks`, commit directly to `main`.

## STEP 4 — Watch Vercel deploy

After you push, Vercel auto-deploys. Open your project → Deployments. You want
to see a green check and **0 errors** on the build. The deployment-checks
section will still say Lint and TypeCheck are "skipped because covered by build"
— that is NORMAL and is what your screenshots already showed (the ✔ blue
checks). The thing that was red before (TypeScript type error in wallet topup)
is fixed, so the build itself will now pass.

## STEP 5 — Test in order

1. Go to your live site → Sign up with a NEW test email.
2. You should land on `/onboarding` (niche picker). Pick "AI tools", type a page
   name, check Instagram + YouTube.
3. Click Start → redirected to `/dashboard`.
4. Open **Wallet** in sidebar → you should see **$1.00 welcome bonus** and
   "$0 spent today".
5. Open **Agent workspace** → empty feed (normal, pipeline isn't writing events
   yet — that's next sprint).
6. Open **Settings** → Channel Connections section should render 7 platform
   cards (no more "Loading connections..." forever).
7. Open **Clone viral** → paste any YouTube URL, choose "Clone the angle", it
   should queue to Studio.
8. Open any of the new tracks (YouTube / TikTok / Affiliate / Store) from the
   dashboard → you should see the step checklist.

If any step fails, send me a screenshot of the EXACT error (URL bar + red
text). I'll fix it in the next message.

## STEP 6 — Railway pipeline re-deploy

Because we changed `pipeline/agent/config.py`, you just need Railway to re-pull
and re-deploy. If your Railway service is connected to the GitHub repo it will
auto-deploy on push. Otherwise: open Railway → your pipeline service →
Deployments → Trigger deploy.

You don't need to change the Dockerfile — ffmpeg and fonts-dejavu are already
in the install line.

---

## What this version does NOT yet wire (next message from me)

These are the backend-to-agent wiring items. The UI is ready for them but the
Python pipeline hasn't been told to write events/charge wallets yet:
- Wallet charging per agent step
- Agent event logging into the `agent_events` Slack feed
- Publishing through YOUR stored YouTube/TikTok/Instagram tokens (it still uses
  the env-var IG for now)
- Brand Bible grounding block injected into every prompt
- Real Stripe webhook (wallet demo mode works even without this)

After you confirm v1.4.1 is live green on Vercel, I will give you the patch for
the Python pipeline that lights up the agent feed + wallet charging. That is
the "agents you can watch working" piece.
