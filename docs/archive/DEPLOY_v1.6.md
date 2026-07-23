# Agent-X v1.6 — Deploy Guide
Multi-project agents + honest idle status + real cost-per-video + agent marketplace with 50% affiliate.

This bundle assumes v1.5 is already deployed (composer OOM fix, real QA gate, Trend Scout).
If you haven't shipped v1.5 yet, deploy it first — v1.6 builds on top of it.

## 1. Run the SQL — in this order
Supabase dashboard → SQL editor:
1. `db/scout.sql` (skip if already run in v1.5)
2. `db/v1.6.sql` — creates `projects`, `marketplace_agents`, `affiliate_links`,
   `affiliate_clicks`, `agent_leads`, seeds 6 original marketplace agents.

Both are idempotent — safe to re-run.

## 2. Copy pipeline files (all replace-in-place)
```
pipeline/agent/ledger.py         (adds item_cost())
pipeline/agent/events.py         (idle_chatter → honest real-state status)
pipeline/agent/strategy.py       (plan/trends accept niche=)
pipeline/agent/brain.py          (write_script accepts context=)
pipeline/agent/scout.py          (active_niches also reads projects table)
pipeline/agent/orchestrator.py   (multi-project planning, cost stamp, weekly planner opt-in)
pipeline/agent/projects.py       (NEW — active_projects())
```
Push to Railway as usual. No new pip dependencies.

## 3. Copy web files (all replace-in-place except marked NEW)
```
web/app/api/studio/route.ts              (queue_topic tags project; +retry_failed)
web/app/api/projects/route.ts            NEW
web/app/dashboard/projects/page.tsx      NEW
web/app/api/marketplace/route.ts         NEW
web/app/dashboard/marketplace/page.tsx   NEW
web/app/api/agent-leads/route.ts         NEW
web/app/r/[code]/route.ts                NEW
web/app/agents/page.tsx                  NEW — public, no login required
web/components/Sidebar.tsx               (adds "Projects" + "Agent marketplace" links)
```
Push to Vercel (or `git push` if auto-deploy is on). Build was verified locally:
`next build` compiles all new routes with zero type errors.

## 4. Env vars — nothing new required
- `WEEKLY_PLANNER=1` (optional) — opt in to the pipeline auto-planning a full week
  of ideas every ~7 days. Off by default. Costs more LLM calls when on.
- `PROJECT_NAME` / `NICHE` — still work as the fallback single-project identity
  if a user never creates a row in `projects`.

## 5. What changed, in plain terms

**Multi-project.** New "Projects" page (Sidebar → Overview → Projects). Create up
to 6 brands/niches per account. The pipeline plans content for every ACTIVE
project on every tick — paused projects cost nothing. The "selected" project is
just where topics you queue by hand get filed; scouting/planning happens for
all active ones regardless.

**No more burned tokens on idle theater.** `idle_chatter()` used to invent
filler dialogue. It now prints your real queue depth, real spend vs. budget,
and how long ago the scout last ran — zero LLM calls, zero cost, still keeps
the Workspace feed alive between jobs.

**Cost-per-video is real now.** After every successful draft, the orchestrator
sums that item's actual `run_ledger` rows and stamps `payload.cost_usd` on it.
You'll see it in Studio next to each drafted item.

**Scripts use real context, not generic fluff.** When a topic comes from a
scouted trend or belongs to a niche project, `brain.write_script()` gets that
context appended to the prompt (trend source URL, project niche/brand) so
scripts are specific instead of defaulting to generic AI-tools angles.

**Agent marketplace.** New public page at `/agents` — six original Agent-X
business agents (support, SDR, content, research, booking, back-office data),
each with a scripted demo preview clearly labeled as scripted (not live AI).
Logged-in users get a personal referral link + code from `/dashboard/marketplace`.

## 6. How the 50% affiliate commission actually works
1. User copies their link: `yoursite.com/r/CODE?a=agent-slug`.
2. Visit → `affiliate_clicks` row logged, 30-day `ax_ref` cookie set, redirect to `/agents`.
3. Visitor fills the lead form on `/agents` → `agent_leads` row created with
   `ref_code` from the cookie (or null if direct/no referrer).
4. **You** (admin) work the lead like any sales lead — this is NOT automated.
   No agent signs contracts or takes payment on its own.
5. When you close it, run:
   ```sql
   update agent_leads set status='closed_won', sale_usd=290
   where id='...';
   ```
   The `trg_fill_commission` trigger auto-sets `commission_usd = sale_usd * 0.5`.
6. Payout is currently **manual** — credit the referrer's wallet by hand
   (there's no Stripe Connect payout flow yet; that's real future work, not
   promised here). `commission_paid` flips to true once you've paid them.

## 7. Two things you should personally decide on before going wide

**Trademark collision.** There is an established product at **agentx.so**
already using the "Agent X" name in a similar space (AI agents / automation).
Running your own "Agent-X" publicly — especially a marketplace selling AI
agents to companies — raises real trademark risk. This bundle does **not**
copy agentx.so's site, copy, or product designs (that would be an IP problem
regardless of the name issue) — everything shipped here (the 6 agents, their
copy, the marketplace UI) is original. But the *name* collision is separate
from originality, and worth a legal look or a rename before you scale
marketing spend behind it.

**"Thousands of MCP integrations."** MCP (Model Context Protocol) is real and
open — Anthropic, GitHub, and others publish MCP servers you can adopt
incrementally (see the GitHub scan below). But claiming "thousands of
integrations" today would be false advertising. Honest scoping: ship one or
two well (e.g. an MCP client in the pipeline that can call a Slack or Google
Sheets MCP server for the back-office agent), and grow the list as you
actually build/test each one.

## 8. GitHub ecosystem scan — worth adopting, roughly by priority
- **punkpeye/awesome-mcp-servers** (91k★) — directory of MCP servers; the
  fastest path to "real" tool integrations for Ledger/Atlas-style agents.
- **github/github-mcp-server** (31k★, MIT) — official GitHub MCP server;
  useful if you ever want agents that can file issues / read repos for devs.
- **microsoft/playwright-mcp** (35k★, Apache-2.0) — browser automation via
  MCP; could power Scout's outbound research with real page rendering instead
  of RSS-only scraping.
- **enescingoz/awesome-n8n-templates** (24k★) — automation recipe patterns;
  good reference for the back-office (Ledger) agent's workflow library, not
  something to literally import.
- **gitroomhq/postiz-app** (33k★, AGPL) — full social scheduling app. AGPL
  means: don't vendor its code into a closed product without understanding
  the copyleft obligations; fine as a feature-inspiration reference only.
None of these were installed — this is a shortlist for you to evaluate, not a
dependency change.

## 9. Manual test checklist after deploy
- [ ] Create a 2nd project on `/dashboard/projects`, confirm it shows "active"
- [ ] Trigger a pipeline tick — confirm Workspace feed shows planning for
      BOTH projects with distinct niches in the log line
- [ ] Let the queue empty — confirm idle status shows real numbers, not chatter
- [ ] Approve a drafted item — confirm `cost_usd` appears on it (live LLM mode only)
- [ ] Visit `/agents` logged out — confirm catalog loads, demo modal works
- [ ] Copy your referral link from `/dashboard/marketplace`, open in a new
      private window, submit the lead form, confirm it appears in your leads table
- [ ] Manually close a lead with `sale_usd` set, confirm `commission_usd` auto-fills at 50%
