-- ============================================================
-- Agent-X v3 UPGRADE — per-account budgets + shot-list ready columns
-- Run ONCE in Supabase SQL Editor (idempotent).
-- ============================================================

-- Per-account budget and settings
alter table public.project_accounts
  add column if not exists daily_budget_usd numeric(10,2) not null default 0.50,
  add column if not exists paused boolean not null default false,
  add column if not exists posts_per_day int not null default 1,
  add column if not exists platforms_config jsonb not null default '{}'::jsonb;

-- Shot-list columns on account_posts for v4 director-level scripts
alter table public.account_posts
  add column if not exists beat_script jsonb,
  add column if not exists video_url text,
  add column if not exists thumbnail_url text,
  add column if not exists published_url text,
  add column if not exists visual_style text,
  add column if not exists errors jsonb not null default '[]'::jsonb;

-- Add a "posts per day" and budget column to projects too
alter table public.projects
  add column if not exists daily_budget_usd numeric(10,2) not null default 2.00;

-- Re-seed marketplace agents if missing (idempotent, duplicates skipped)
insert into public.marketplace_agents (slug, name, tagline, description, category, price_usd, capabilities, demo_script)
select 'atlas-research','Atlas — Research Analyst Agent','Digest of any market, competitor or topic with cited sources.',
       'Atlas reads links/files you provide plus public sources, and returns structured briefs with findings, quotes, and a source list.',
       'Research',240,'["Structured briefs with citations","Competitor snapshots","File & link ingestion","Fact vs inference separation","Weekly watchlist digests"]'::jsonb,
       '[{"q":"Summarize my 3 competitors pricing","a":"Send the three URLs. I will return a table of plans, limits and positioning, each cell linked to the exact section."}]'::jsonb
where not exists (select 1 from marketplace_agents where slug='atlas-research');

select 'v3 upgrade applied' as status;
