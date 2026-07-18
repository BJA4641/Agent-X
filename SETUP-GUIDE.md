# Agent-X Upgrade v0.3 — Multi-tenant SaaS Layer

This upgrade adds three critical features to Agent-X without breaking existing
single-tenant operation:

1. **Per-user Channel Connections** — users connect their own Instagram, YouTube,
   TikTok, X, LinkedIn, Pinterest, Facebook from Settings (encrypted at rest)
2. **Brand Bible Agent** — every client gets a distinct voice, audience, pillar
   set, visual ID, and risk register (ends "everyone sounds the same")
3. **QA Gate + Planner Calendar** — 12-point editor-in-chief runs before publish;
   7-day editorial calendar balances pillars and content mix

## How to apply (do this OUTSIDE github, on your local clone)

1. Download this zip and unzip it somewhere (e.g., your Downloads folder).
2. In a terminal:

   ```bash
   cd /path/to/your/local/Agent-X   # your existing clone
   # Copy in new files (does not overwrite anything except settings page
   # which you already have a git history for — 'git diff' will show the change)
   cp -r ~/Downloads/Agent-X-upgrade/db            ./
   cp -r ~/Downloads/Agent-X-upgrade/pipeline/agent/*.py   ./pipeline/agent/
   cp -r ~/Downloads/Agent-X-upgrade/prompts/*.md          ./prompts/
   cp -r ~/Downloads/Agent-X-upgrade/web/components/*.tsx  ./web/components/
   mkdir -p ./web/app/api/connections
   cp ~/Downloads/Agent-X-upgrade/web/app/api/connections/route.ts  ./web/app/api/connections/
   # Replace existing files (review these with `git diff` after copying)
   cp ~/Downloads/Agent-X-upgrade/web/app/dashboard/settings/page.tsx  ./web/app/dashboard/settings/page.tsx
   cp ~/Downloads/Agent-X-upgrade/PATCHED-original-files/pipeline/agent/orchestrator.py ./pipeline/agent/orchestrator.py
   cp ~/Downloads/Agent-X-upgrade/PATCHED-original-files/pipeline/agent/publishing.py   ./pipeline/agent/publishing.py
   cp ~/Downloads/Agent-X-upgrade/PATCHED-original-files/pipeline/agent/analytics.py    ./pipeline/agent/analytics.py
   cp ~/Downloads/Agent-X-upgrade/PATCHED-original-files/pipeline/agent/community.py    ./pipeline/agent/community.py
   ```

3. Add `cryptography` to pipeline requirements (used by connections.py local-
   encryption fallback; optional but recommended):

   ```bash
   echo "cryptography>=43.0.0" >> pipeline/requirements.txt
   ```

4. Commit and push:

   ```bash
   git add -A
   git commit -m "v0.3 multi-tenant channels + Brand Bible + QA gate"
   git push
   ```

5. Vercel and Railway auto-deploy from your repo. The new web code deploys
   safely even before you run the SQL migrations — it just returns empty
   connection states until the DB schema exists.

## Steps AFTER GitHub (run once, in order)

### 1. Run SQL migrations in Supabase
Open Supabase → SQL editor. In this order:

```sql
-- A. Generate a 32-byte encryption key (run this once)
select encode(gen_random_bytes(32), 'hex') as encryption_key;
-- Copy the hex string output, then run:
alter database postgres set app.encryption_key to '<PASTE HEX KEY HERE>';

-- B. Apply the schema patch
-- Open db/patches/001_connections_and_brand.sql and run the whole file.
-- Open db/patches/002_encryption_helpers.sql and run the whole file.
```

### 2. Supabase Storage
Create a new **private** bucket named `connections` (not needed — tokens are in
the DB). The existing `media` public bucket stays as is.

### 3. Environment variables
Add to Railway worker env:
```
CONN_ENC_KEY=<same hex key as in Postgres, only if using Fernet fallback>
# (Optional) brand defaults for single-tenant mode
BRAND_NAME=
BRAND_VERTICAL=
VOICE_FORMALITY=conversational
CTA_LINE=Follow for one AI move a day.
```

No new vars needed on Vercel — the web route uses the existing
SUPABASE_SERVICE_ROLE_KEY for server-side encryption calls.

### 4. Test the Settings page
1. Sign into your app as the admin email
2. Open `/dashboard/settings`
3. You should see a new "Channel connections" section with 7 platform cards,
   each showing "○ not connected" with a Connect button.
4. Try pasting a dummy access token and clicking Connect — refresh, and the
   card should flip to "● connected".
5. Verify that the DB row is encrypted: open Supabase Table Editor →
   `user_connections` — `credentials` should be `{}` and `cred_enc` should be
   a long base64 string. Good.

### 5. Test QA gate + Brand Bible (single-tenant mode works immediately)
- Locally: `cd pipeline && python cli.py tick --stub` — the tick output should
  now show `[planner] queued ...` lines (calendar build) and a QA score log.
- Without filling out a Brand Bible it uses a default voice, so existing
  behavior is preserved.

### 6. Build the Brand Onboarding flow (next sprint)
The agent/brand.py module is ready to call. Add these when you want to
complete onboarding:

1. Add a web page `/dashboard/brand` with the 10 questions from
   `pipeline/agent/brand.py` QUESTIONNAIRE list.
2. Add an API route `/api/brand` that calls `brand.generate_from_answers()` via
   a serverless function or via the Celery worker.
3. After a user completes onboarding, their `brand_profiles.onboarding_done`
   flips to true and every subsequent prompt uses their grounding block.

### 7. True one-click OAuth (later)
The current ChannelConnections component asks users to paste tokens. For one-
click OAuth ("Connect with Instagram" button), add OAuth redirect routes:
- `/api/oauth/{platform}/start` → redirects to platform consent screen
- `/api/oauth/{platform}/callback` → exchanges code for token, encrypts, saves
All major platforms support this; all the storage and UI is already in place.

### 8. Optional: add `cryptography` to the worker
Railway Dockerfile: add `RUN pip install cryptography` after the existing pip
line. This is only needed if you want to encrypt/decrypt tokens from within
the Python worker without going through Postgres RPC; the RPC approach works
without it.

## What's safe to do last (no urgency)
- TikTok/LinkedIn/X/Pinterest/Facebook publish functions — the platform UI is
  there, creds can be saved, but actual upload dispatch for those platforms
  returns "not yet implemented" until you add their API code. Instagram and
  YouTube publish already work.
- Carousel / Stories / Threads production (current pipeline only does vertical
  video shorts; planner marks them but composer needs to handle new formats).
- A/B testing framework (planner already tags hook_type; add statistical
  significance in analytics and feed winners back to strategy).

## Rollback
If anything goes wrong: `git revert <commit>` and push. The new DB tables are
additive — they don't interfere with existing board_items/run_ledger/settings.
