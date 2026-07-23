# Agent-X v1.4 — Deploy Instructions

## ONE-TIME SETUP (15 minutes)

### Step 1: Run the SQL
Open Supabase → SQL Editor → New Query.
**Copy and paste the entire contents of `db/setup_v1.4.sql` and click Run.**
Do NOT run the old patch files. This ONE file sets up everything:
- Encryption functions (pgcrypto AES-256)
- profiles (niche + onboarding state)
- user_connections (encrypted OAuth tokens)
- brand_profiles (Brand Bible)
- wallets + wallet_transactions (token billing)
- agent_events (Slack-style agent feed)
- niches (20 pre-populated niches)
- Auto-profile creation trigger on signup

You will see "setup complete" in the results. If you see any errors, copy them to Claude.

### Step 2: Storage buckets (Supabase Dashboard → Storage)
Create three buckets:
- `media`  — public (Instagram needs public URLs)
- `proofs` — private (course verification screenshots)
- `agent-avatars` — public (optional future feature)

### Step 3: Copy web files
Copy these files from the zip to your repo, matching the folder structure:
- `web/components/ChannelConnections.tsx` (replace existing)
- `web/components/Sidebar.tsx` (replace existing)
- `web/app/api/connections/route.ts` (new file)
- `web/app/api/me/profile/route.ts` (new folder + file)
- `web/app/api/wallet/route.ts` (new folder + file)
- `web/app/api/wallet/topup/route.ts` (new folder + file)
- `web/app/api/workspace/events/route.ts` (new folder + file)
- `web/app/onboarding/page.tsx` (new folder + file)
- `web/app/wallet/page.tsx` (new folder + file)
- `web/app/clone/page.tsx` (new folder + file)
- `web/app/workspace/page.tsx` (new folder + file)

### Step 4: Update existing files
- In `web/app/dashboard/settings/page.tsx`: the ChannelConnections import and usage is already correct in the file that's on your repo (you uploaded it earlier). Verify it shows `<ChannelConnections />` under the "Channel connections" heading.
- In `web/app/dashboard/layout.tsx`: add a redirect to /onboarding for new users. Simplest change:
  ```tsx
  // After getting user:
  const { data: profile } = await sb.from("profiles").select("onboarded").eq("user_id", user.id).maybeSingle();
  if (!profile?.onboarded) redirect("/onboarding");
  ```
  And import the new Sidebar from `@/components/Sidebar` (which supports `onboarded`).

### Step 5: Push and Deploy
```bash
git add -A
git commit -m "v1.4: onboarding, wallet, agent workspace, channel connections, clone module"
git push
```
Vercel auto-deploys. Railway auto-deploys the pipeline (pipeline doesn't need changes yet — it keeps working as before).

### Step 6: Test
1. Sign up with a new email → should land on `/onboarding`
2. Pick niche (e.g. AI tools) → redirected to dashboard
3. Open Wallet → see $1.00 welcome bonus
4. Open Agent Workspace → empty feed (will populate as agents work)
5. Open Settings → Channel connections → cards should render (not "Loading..." forever)
6. Open Clone viral → paste any YT URL → adds to Studio

## What's in this version
- **Onboarding flow** (niche picker with 20 niches, page name, platform choice)
- **Wallet system** with Stripe checkout (falls back to demo mode if Stripe key missing — adds credit directly for testing), per-action costs, transaction history, daily spend bar
- **Agent Workspace** (Slack-style live feed of agent actions, per-agent filter, stats)
- **Channel Connections UI** fixed (no more stuck "Loading...", error states, 7 platforms)
- **Encrypted token storage** (AES-256 via pgcrypto, secret stored in DB settings, browser never sees secrets)
- **Clone viral** module (angle-clone mode recommended; mirror mode warned against)
- **Sidebar reorg** (Create / Monetize / Account groups, Agent Workspace, Wallet links)
- **Auto-profile trigger** (every new signup gets a profile row + $1 welcome credit)

## What comes next (tell Claude to do these after v1.4 is live)
1. Wire the pipeline to actually charge wallets (pipeline reads user balance, inserts wallet_transactions for each step, refuses to produce if balance=0)
2. Add Brand Bible onboarding questions (10 questions from `pipeline/agent/brand.py`)
3. Multi-platform trend sources (TikTok, Reddit, Instagram hashtags)
4. Real Stripe webhook to credit wallet on payment
5. Instagram OAuth one-click connect (replace paste-token flow with Meta OAuth)
6. YouTube publish through user-stored tokens (pipeline reads from connections table)
7. Agent event logging from the pipeline (insert into agent_events at every step)
