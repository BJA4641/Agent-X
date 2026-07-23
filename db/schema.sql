-- =====================================================================
-- Agent-X CANONICAL SCHEMA — snapshot of the LIVE database (worker v5.9.4)
-- Generated 2026-07-23 directly from Supabase project qrzwoumhfxdwozpasxsn
-- via information_schema/pg_catalog.
--
-- This file REPLACES all earlier db/schema.sql versions, which had
-- drifted badly behind the incremental v1→v5.9 migrations.
--
-- SECURITY MODEL (verified live 2026-07-23):
--   · RLS is ENABLED on every table.
--   · The Python worker and the web API routes use the SERVICE-ROLE key,
--     which bypasses RLS.
--   · The anon/public key can read nothing unless a policy grants it.
--   · User-facing tables (profiles, wallets, task_progress, entitlements,
--     user_connections, ...) carry per-user policies added in v5.9.x.
--
-- NOTE: timestamps in jobs/jobs_archive/worker_health are UNIX EPOCH
-- doubles (not timestamptz). Cast with to_timestamp() when reading.
--
-- This file is idempotent (create table if not exists) and safe to run
-- on a fresh database to recreate the full v5.9.4 structure.
-- =====================================================================

create table if not exists account_documents (
  id uuid not null default gen_random_uuid(),
  account_id uuid not null,
  doc_type text not null,
  content text not null,
  agent text not null default 'architect'::text,
  version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table account_documents enable row level security;

create table if not exists account_posts (
  id uuid not null default gen_random_uuid(),
  account_id uuid not null,
  post_type text not null,
  title text not null,
  hook text,
  script text,
  caption text not null,
  visual_prompt text,
  hashtags text[] not null default '{}'::text[],
  duration_seconds integer default 30,
  scheduled_at timestamptz,
  status text not null default 'planned'::text,
  created_by_agent text not null default 'strategist'::text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  first_comment text,
  alt_text text,
  yt_title text,
  seo_keywords jsonb not null default '[]'::jsonb
);
alter table account_posts enable row level security;

create table if not exists affiliate_clicks (
  id bigint generated always as identity,
  code text not null,
  agent_slug text,
  created_at timestamptz not null default now()
);
alter table affiliate_clicks enable row level security;

create table if not exists affiliate_links (
  id uuid not null default gen_random_uuid(),
  user_id uuid,
  code text not null,
  created_at timestamptz not null default now()
);
alter table affiliate_links enable row level security;

create table if not exists agent_events (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  user_id uuid,
  agent text not null default 'system'::text,
  action text not null default 'note'::text,
  item_id uuid,
  message text,
  status text not null default 'info'::text,
  cost_usd numeric not null default 0,
  created_at timestamptz not null default now(),
  ts double precision not null default EXTRACT(epoch FROM now()),
  emitter text not null default 'system'::text,
  type text not null default 'agent.info'::text,
  subject jsonb not null default '{}'::jsonb,
  job_id text,
  brand_id uuid,
  account_id uuid,
  cost_cents integer not null default 0,
  data jsonb not null default '{}'::jsonb
);
alter table agent_events enable row level security;

create table if not exists agent_leads (
  id uuid not null default gen_random_uuid(),
  agent_slug text not null,
  name text not null,
  email text not null,
  company text,
  message text,
  ref_code text,
  status text not null default 'new'::text,
  sale_usd numeric,
  commission_usd numeric,
  commission_paid boolean not null default false,
  created_at timestamptz not null default now()
);
alter table agent_leads enable row level security;

create table if not exists asset_library (
  id text not null,
  tenant_id text not null default 'me'::text,
  account_id uuid,
  niche text,
  asset_type text not null,
  content text not null,
  blob_path text,
  metadata jsonb not null default '{}'::jsonb,
  tags text[] not null default '{}'::text[],
  usage_count integer not null default 0,
  last_used_at timestamptz,
  performance_score numeric,
  cost_to_make_usd numeric not null default 0,
  created_at timestamptz not null default now()
);
alter table asset_library enable row level security;

create table if not exists board_items (
  id uuid not null default gen_random_uuid(),
  tenant_id text not null default 'me'::text,
  status text not null default 'idea'::text,
  topic text not null,
  payload jsonb not null default '{}'::jsonb,
  scheduled_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  account_id uuid
);
alter table board_items enable row level security;

create table if not exists brand_profiles (
  user_id uuid not null,
  brand_name text,
  vertical text,
  voice_tone jsonb not null default '{}'::jsonb,
  audience jsonb not null default '[]'::jsonb,
  pillars jsonb not null default '[]'::jsonb,
  visual_id jsonb not null default '{}'::jsonb,
  do_list jsonb not null default '[]'::jsonb,
  dont_list jsonb not null default '[]'::jsonb,
  cta_line text default 'Follow for more.'::text,
  risk_register jsonb not null default '[]'::jsonb,
  onboarding_done boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table brand_profiles enable row level security;

create table if not exists capital_allocation (
  tenant_id text not null default 'me'::text,
  account_id uuid not null,
  day date not null default CURRENT_DATE,
  budget_usd numeric not null default 0,
  max_posts integer not null default 0,
  focus text not null default 'balanced'::text,
  note text not null default ''::text,
  model_tier text not null default 'mix'::text,
  approved_by text not null default 'ceo'::text,
  decided_at timestamptz not null default now()
);
alter table capital_allocation enable row level security;

create table if not exists ceo_recommendations (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  ts timestamptz not null default now(),
  day date not null default CURRENT_DATE,
  severity text not null default 'info'::text,
  category text not null,
  account_id uuid,
  recommendation text not null,
  reasoning text not null,
  projected_roi numeric,
  projected_value_usd numeric,
  action_url text,
  applied boolean not null default false,
  dismissed boolean not null default false,
  created_at timestamptz not null default now()
);
alter table ceo_recommendations enable row level security;

create table if not exists content_grades (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  post_id uuid,
  item_id uuid,
  grader text not null default 'grader'::text,
  hook integer not null,
  visuals integer not null,
  pacing integer not null,
  audio integer not null,
  caption integer not null,
  cta integer not null,
  overall numeric not null,
  passed boolean not null default false,
  notes text,
  fix_instruction text,
  created_at timestamptz not null default now()
);
alter table content_grades enable row level security;

create table if not exists entitlements (
  user_id uuid not null,
  module_id text not null,
  stripe_session text,
  created_at timestamptz not null default now()
);
alter table entitlements enable row level security;

create table if not exists escalations (
  id uuid not null default gen_random_uuid(),
  tenant_id text not null default 'me'::text,
  job_id text,
  item_id uuid,
  account_id uuid,
  severity text not null default 'ask'::text,
  summary text not null,
  options jsonb not null default '[]'::jsonb,
  context jsonb not null default '{}'::jsonb,
  resolution text,
  resolved_by uuid,
  resolved_note text,
  created_at timestamptz not null default now(),
  resolved_at timestamptz,
  deadline_hours double precision not null default 24
);
alter table escalations enable row level security;

create table if not exists exec_decisions (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  ts timestamptz not null default now(),
  account_id uuid,
  job_id text,
  department text not null,
  action text not null,
  estimated_cost_usd numeric not null default 0,
  expected_value_usd numeric,
  expected_roi numeric,
  success_probability numeric,
  decision text not null default 'approve'::text,
  reason text not null default ''::text,
  cheaper_alternative text,
  reuse_asset_id text,
  model_selected text,
  created_at timestamptz not null default now()
);
alter table exec_decisions enable row level security;

create table if not exists experiments (
  id uuid not null default gen_random_uuid(),
  tenant_id text not null default 'me'::text,
  account_id uuid,
  item_id uuid,
  topic text not null,
  variants jsonb not null,
  winner text,
  winning_reason text,
  status text not null default 'running'::text,
  decision_at timestamptz,
  created_at timestamptz not null default now()
);
alter table experiments enable row level security;

create table if not exists jobs (
  id text not null,
  job_type text not null,
  brand_id uuid,
  account_id uuid,
  project_id uuid,
  priority integer not null default 50,
  status text not null default 'queued'::text,
  payload jsonb not null default '{}'::jsonb,
  result jsonb,
  attempts integer not null default 0,
  max_attempts integer not null default 2,
  parent_job_id text,
  requested_by text not null default 'system'::text,
  worker_id text,
  scheduled_for double precision not null default EXTRACT(epoch FROM now()),
  deadline double precision,
  error text,
  cost_cents integer not null default 0,
  idempotency_key text,
  created_at double precision not null default EXTRACT(epoch FROM now()),
  claimed_at double precision,
  finished_at double precision,
  started_at double precision,
  last_heartbeat_at double precision
);
alter table jobs enable row level security;

create table if not exists jobs_archive (
  id text not null,
  job_type text not null,
  brand_id uuid,
  account_id uuid,
  project_id uuid,
  priority integer not null default 50,
  status text not null default 'queued'::text,
  payload jsonb not null default '{}'::jsonb,
  result jsonb,
  attempts integer not null default 0,
  max_attempts integer not null default 2,
  parent_job_id text,
  requested_by text not null default 'system'::text,
  worker_id text,
  scheduled_for double precision not null default EXTRACT(epoch FROM now()),
  deadline double precision,
  error text,
  cost_cents integer not null default 0,
  idempotency_key text,
  created_at double precision not null default EXTRACT(epoch FROM now()),
  claimed_at double precision,
  finished_at double precision,
  started_at double precision,
  last_heartbeat_at double precision
);
alter table jobs_archive enable row level security;

create table if not exists kpi_snapshots (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  ts timestamptz not null default now(),
  metric text not null,
  value numeric not null default 0,
  dimensions jsonb not null default '{}'::jsonb
);
alter table kpi_snapshots enable row level security;

create table if not exists lessons (
  id uuid not null default gen_random_uuid(),
  tenant_id text not null default 'me'::text,
  scope text not null,
  subject_id text,
  topic text not null,
  lesson text not null,
  evidence jsonb not null default '{}'::jsonb,
  confidence double precision not null default 0.5,
  applied_at timestamptz,
  created_at timestamptz not null default now()
);
alter table lessons enable row level security;

create table if not exists marketplace_agents (
  id uuid not null default gen_random_uuid(),
  slug text not null,
  name text not null,
  tagline text,
  description text,
  category text,
  price_usd numeric not null default 0,
  capabilities jsonb not null default '[]'::jsonb,
  demo_script jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default now()
);
alter table marketplace_agents enable row level security;

create table if not exists mcp_connections (
  id uuid not null default gen_random_uuid(),
  user_id uuid not null,
  provider text not null,
  label text,
  access_token text not null,
  scopes text[] not null default '{}'::text[],
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
alter table mcp_connections enable row level security;

create table if not exists memory (
  id uuid not null default gen_random_uuid(),
  tenant_id text not null default 'me'::text,
  account_id uuid,
  project_id uuid,
  brand_id uuid,
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
alter table memory enable row level security;

create table if not exists memory_entries (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  project_id uuid,
  account_id uuid,
  role text not null,
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
alter table memory_entries enable row level security;

create table if not exists niches (
  tenant_id text not null default 'me'::text,
  slug text not null,
  name text not null,
  keywords text not null default ''::text,
  channels text not null default ''::text,
  created_at timestamptz default now(),
  emoji text,
  starter_channels text[] default '{}'::text[],
  starter_queries text[] default '{}'::text[],
  description text
);
alter table niches enable row level security;

create table if not exists performance (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  item_id uuid,
  platform text not null,
  views integer default 0,
  likes integer default 0,
  comments integer default 0,
  captured_at timestamptz not null default now()
);
alter table performance enable row level security;

create table if not exists profiles (
  user_id uuid not null,
  display_name text,
  niche text,
  page_name text,
  platforms text[] default '{}'::text[],
  onboarding_step integer not null default 0,
  onboarded boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table profiles enable row level security;

create table if not exists project_accounts (
  id uuid not null default gen_random_uuid(),
  project_id uuid not null,
  user_id uuid not null,
  name text not null,
  handle text not null,
  platforms jsonb not null default '["instagram", "tiktok", "youtube_shorts"]'::jsonb,
  niche text not null,
  status text not null default 'needs_setup'::text,
  avatar_emoji text default '🤖'::text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  paused boolean not null default false,
  daily_budget_usd numeric not null default 0.50,
  posts_per_day integer not null default 1,
  platforms_config jsonb not null default '{}'::jsonb,
  config jsonb not null default '{}'::jsonb,
  brand_bible jsonb,
  affiliate_urls jsonb not null default '[]'::jsonb,
  sponsor text
);
alter table project_accounts enable row level security;

create table if not exists projects (
  id uuid not null default gen_random_uuid(),
  user_id uuid,
  name text not null,
  niche text,
  platforms jsonb not null default '[]'::jsonb,
  status text not null default 'active'::text,
  cta text,
  created_at timestamptz not null default now(),
  paused boolean not null default false,
  daily_budget_usd numeric not null default 2.00
);
alter table projects enable row level security;

create table if not exists revenue_events (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  account_id uuid,
  item_id text,
  amount_usd numeric not null default 0,
  source text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
alter table revenue_events enable row level security;

create table if not exists roi_snapshots (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  account_id uuid not null,
  day date not null default CURRENT_DATE,
  spend_usd numeric not null default 0,
  posts_published integer not null default 0,
  posts_planned integer not null default 0,
  scripts_written integer not null default 0,
  images_generated integer not null default 0,
  videos_generated integer not null default 0,
  api_calls integer not null default 0,
  views numeric not null default 0,
  likes numeric not null default 0,
  comments numeric not null default 0,
  shares numeric not null default 0,
  saves numeric not null default 0,
  followers_gained numeric not null default 0,
  revenue_usd numeric not null default 0,
  affiliate_clicks integer not null default 0,
  affiliate_conversions integer not null default 0,
  sponsorship_revenue_usd numeric not null default 0,
  product_revenue_usd numeric not null default 0,
  roi_multiple numeric,
  cost_per_follower numeric,
  cost_per_view numeric,
  cost_per_engagement numeric,
  created_at timestamptz not null default now()
);
alter table roi_snapshots enable row level security;

create table if not exists run_ledger (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  item_id uuid,
  step text not null,
  model text,
  prompt_version text,
  cost_usd numeric not null default 0,
  ok boolean not null default true,
  detail text,
  created_at timestamptz not null default now(),
  job_id text,
  account_id uuid,
  provider_label text,
  cost_cents integer not null default 0,
  department text,
  action text
);
alter table run_ledger enable row level security;

create table if not exists settings (
  tenant_id text not null default 'me'::text,
  key text not null,
  value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table settings enable row level security;

create table if not exists task_progress (
  user_id uuid not null,
  task_key text not null,
  done boolean not null default false,
  proof jsonb,
  updated_at timestamptz not null default now()
);
alter table task_progress enable row level security;

create table if not exists trend_items (
  id bigint generated always as identity,
  tenant_id text not null default 'me'::text,
  niche text not null default 'ai_tools'::text,
  platform text not null default 'news'::text,
  title text not null,
  url text not null,
  author text,
  views bigint not null default 0,
  engagement bigint not null default 0,
  heat integer not null default 0,
  published_at timestamptz,
  scraped_at timestamptz not null default now()
);
alter table trend_items enable row level security;

create table if not exists user_connections (
  user_id uuid not null,
  platform text not null,
  display_name text,
  credentials_json jsonb not null default '{}'::jsonb,
  cred_enc text,
  status text not null default 'active'::text,
  last_test_at timestamptz,
  error_message text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table user_connections enable row level security;

create table if not exists waitlist (
  email text not null,
  note text,
  created_at timestamptz not null default now()
);
alter table waitlist enable row level security;

create table if not exists wallet_transactions (
  id bigint generated always as identity,
  user_id uuid not null,
  type text not null,
  amount numeric not null default 0,
  step text,
  item_id uuid,
  note text,
  stripe_payment_id text,
  created_at timestamptz not null default now()
);
alter table wallet_transactions enable row level security;

create table if not exists wallets (
  user_id uuid not null,
  balance_usd numeric not null default 0,
  lifetime_spent numeric not null default 0,
  lifetime_topup numeric not null default 0,
  overdraft_limit numeric not null default 0,
  paused boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table wallets enable row level security;

create table if not exists worker_health (
  worker_id text not null,
  tenant_id text not null default 'me'::text,
  started_at double precision not null default EXTRACT(epoch FROM now()),
  last_heartbeat_at double precision not null default EXTRACT(epoch FROM now()),
  jobs_completed integer not null default 0,
  jobs_failed integer not null default 0,
  jobs_in_progress integer not null default 0,
  last_error text,
  host text,
  version text
);
alter table worker_health enable row level security;

-- ---------------------------------------------------------------------
-- PRIMARY KEYS (as they exist live; wrap in DO blocks if re-running on
-- a database that already has them)
-- ---------------------------------------------------------------------
alter table account_documents add primary key (id);
alter table account_posts add primary key (id);
alter table affiliate_clicks add primary key (id);
alter table affiliate_links add primary key (id);
alter table agent_events add primary key (id);
alter table agent_leads add primary key (id);
alter table asset_library add primary key (id);
alter table board_items add primary key (id);
alter table brand_profiles add primary key (user_id);
alter table capital_allocation add primary key (tenant_id, account_id, day);
alter table ceo_recommendations add primary key (id);
alter table content_grades add primary key (id);
alter table entitlements add primary key (user_id, module_id);
alter table escalations add primary key (id);
alter table exec_decisions add primary key (id);
alter table experiments add primary key (id);
alter table jobs add primary key (id);
alter table jobs_archive add primary key (id);
alter table kpi_snapshots add primary key (id);
alter table lessons add primary key (id);
alter table marketplace_agents add primary key (id);
alter table mcp_connections add primary key (id);
alter table memory add primary key (id);
alter table memory_entries add primary key (id);
alter table niches add primary key (tenant_id, slug);
alter table performance add primary key (id);
alter table profiles add primary key (user_id);
alter table project_accounts add primary key (id);
alter table projects add primary key (id);
alter table revenue_events add primary key (id);
alter table roi_snapshots add primary key (id);
alter table run_ledger add primary key (id);
alter table settings add primary key (tenant_id, key);
alter table task_progress add primary key (user_id, task_key);
alter table trend_items add primary key (id);
alter table user_connections add primary key (user_id, platform);
alter table waitlist add primary key (email);
alter table wallet_transactions add primary key (id);
alter table wallets add primary key (user_id);
alter table worker_health add primary key (worker_id);

-- ---------------------------------------------------------------------
-- VIEW: v_account_brief — account + its brand documents at a glance
-- (views do not carry RLS; access is governed by underlying tables)
-- ---------------------------------------------------------------------
create or replace view v_account_brief as
 SELECT id AS account_id, project_id, name, handle, niche, paused,
    posts_per_day, daily_budget_usd,
    ( SELECT d.content FROM account_documents d
       WHERE d.account_id = a.id AND d.doc_type = 'executive_summary' LIMIT 1) AS executive_summary,
    ( SELECT d.content FROM account_documents d
       WHERE d.account_id = a.id AND d.doc_type = 'brand_identity' LIMIT 1) AS brand_identity,
    ( SELECT d.content FROM account_documents d
       WHERE d.account_id = a.id AND d.doc_type = 'tone_guide' LIMIT 1) AS tone_guide,
    ( SELECT d.content FROM account_documents d
       WHERE d.account_id = a.id AND d.doc_type = 'visual_identity' LIMIT 1) AS visual_identity,
    ( SELECT d.content FROM account_documents d
       WHERE d.account_id = a.id AND d.doc_type = 'content_rules' LIMIT 1) AS content_rules,
    ( SELECT count(*) FROM account_documents d
       WHERE d.account_id = a.id) AS docs_count
   FROM project_accounts a;
