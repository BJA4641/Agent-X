-- ======================================================
-- v5.3 PRODUCTION MIGRATION (FIXED ORDER — idempotent)
-- Run in Supabase SQL editor. Safe to re-run.
--
-- FIXES vs earlier v5.3 file:
--   * CREATE TABLE IF NOT EXISTS now runs FIRST (before any ALTER/CREATE INDEX)
--     so the script works even on a DB where jobs/agent_events were never created
--     (which is your case because v5.0 raised a syntax error and v5.2 had the
--     IMMUTABLE-index error, so the v5 tables never got built).
--   * Zero PL/pgSQL, zero DO $$ blocks.
--   * Zero partial indexes using STABLE functions (fixes v5.2's IMMUTABLE error).
-- ======================================================

-- ======================================================
-- STEP 1 (of 9): Create all v5 tables FIRST if missing.
--                 (On an existing DB every line here is a no-op.)
-- ======================================================
create table if not exists public.jobs (
    id text primary key, job_type text not null,
    brand_id uuid, account_id uuid, project_id uuid,
    priority int not null default 50,
    status text not null default 'queued',
    payload jsonb not null default '{}'::jsonb, result jsonb,
    attempts int not null default 0, max_attempts int not null default 2,
    parent_job_id text, requested_by text not null default 'system', worker_id text,
    scheduled_for float not null default extract(epoch from now()), deadline float,
    error text, cost_cents int not null default 0, idempotency_key text unique,
    created_at float not null default extract(epoch from now()),
    claimed_at float, finished_at float, started_at float, last_heartbeat_at float
);

create table if not exists public.agent_events (
    id text primary key default substr(md5(random()::text || clock_timestamp()::text),1,12),
    tenant_id text not null default 'me', ts float not null default extract(epoch from now()),
    emitter text not null, type text not null default 'agent.info',
    status text not null default 'info', action text not null default '', message text not null default '',
    subject jsonb not null default '{}'::jsonb, job_id text, brand_id uuid, account_id uuid,
    cost_cents int not null default 0, data jsonb not null default '{}'::jsonb,
    item_id uuid references board_items(id) on delete set null,
    user_id uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now()
);

create table if not exists public.memory (
    id uuid primary key default gen_random_uuid(), tenant_id text not null default 'me',
    account_id uuid, project_id uuid, brand_id uuid,
    role text not null, content text not null, metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.lessons (
    id uuid primary key default gen_random_uuid(), tenant_id text not null default 'me',
    scope text not null, subject_id text, topic text not null, lesson text not null,
    evidence jsonb not null default '{}'::jsonb, confidence float not null default 0.5,
    applied_at timestamptz, created_at timestamptz not null default now()
);

create table if not exists public.experiments (
    id uuid primary key default gen_random_uuid(), tenant_id text not null default 'me',
    account_id uuid, item_id uuid references board_items(id) on delete set null,
    topic text not null, variants jsonb not null, winner text, winning_reason text,
    status text not null default 'running', decision_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists public.escalations (
    id uuid primary key default gen_random_uuid(), tenant_id text not null default 'me',
    job_id text, item_id uuid references board_items(id) on delete set null, account_id uuid,
    severity text not null default 'ask', summary text not null,
    options jsonb not null default '[]'::jsonb, context jsonb not null default '{}'::jsonb,
    resolution text, resolved_by uuid references auth.users(id) on delete set null,
    resolved_note text, created_at timestamptz not null default now(),
    resolved_at timestamptz, deadline_hours float not null default 24
);

create table if not exists public.worker_health (
    worker_id text primary key, tenant_id text not null default 'me',
    started_at float not null default extract(epoch from now()),
    last_heartbeat_at float not null default extract(epoch from now()),
    jobs_completed int not null default 0, jobs_failed int not null default 0,
    jobs_in_progress int not null default 0, last_error text, host text, version text
);

create table if not exists public.kpi_snapshots (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me', ts timestamptz not null default now(),
    metric text not null, value numeric(14,4) not null default 0,
    dimensions jsonb not null default '{}'::jsonb
);

create table if not exists public.trend_items (
    id uuid primary key default gen_random_uuid(), tenant_id text not null default 'me',
    title text not null, url text, platform text, niche text, heat float not null default 0,
    angle text, metadata jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
);

create table if not exists public.account_documents (
    account_id uuid not null, doc_type text not null, content text not null default '',
    updated_at timestamptz not null default now(), primary key (account_id, doc_type)
);

-- ======================================================
-- STEP 2: jobs columns — fill any columns that a partial
--         older migration might have missed. All IF NOT EXISTS.
-- ======================================================
alter table public.jobs add column if not exists id text;
alter table public.jobs add column if not exists job_type text;
alter table public.jobs add column if not exists brand_id uuid;
alter table public.jobs add column if not exists account_id uuid;
alter table public.jobs add column if not exists project_id uuid;
alter table public.jobs add column if not exists priority int not null default 50;
alter table public.jobs add column if not exists payload jsonb not null default '{}'::jsonb;
alter table public.jobs add column if not exists result jsonb;
alter table public.jobs add column if not exists attempts int not null default 0;
alter table public.jobs add column if not exists max_attempts int not null default 2;
alter table public.jobs add column if not exists parent_job_id text;
alter table public.jobs add column if not exists requested_by text not null default 'system';
alter table public.jobs add column if not exists worker_id text;
alter table public.jobs add column if not exists scheduled_for float not null default extract(epoch from now());
alter table public.jobs add column if not exists deadline float;
alter table public.jobs add column if not exists error text;
alter table public.jobs add column if not exists cost_cents int not null default 0;
alter table public.jobs add column if not exists idempotency_key text;
alter table public.jobs add column if not exists created_at float not null default extract(epoch from now());
alter table public.jobs add column if not exists claimed_at float;
alter table public.jobs add column if not exists finished_at float;
alter table public.jobs add column if not exists started_at float;
alter table public.jobs add column if not exists last_heartbeat_at float;
alter table public.jobs add column if not exists status text not null default 'queued';

-- jobs status check
alter table public.jobs drop constraint if exists jobs_status_check;
alter table public.jobs add constraint jobs_status_check
    check (status in ('queued','claimed','in_progress','wait_human','done','failed','blocked'));

-- ======================================================
-- STEP 3: agent_events columns
-- ======================================================
alter table public.agent_events add column if not exists id text;
alter table public.agent_events add column if not exists tenant_id text not null default 'me';
alter table public.agent_events add column if not exists ts float not null default extract(epoch from now());
alter table public.agent_events add column if not exists emitter text not null default 'system';
alter table public.agent_events add column if not exists type text not null default 'agent.info';
alter table public.agent_events add column if not exists status text not null default 'info';
alter table public.agent_events add column if not exists action text not null default '';
alter table public.agent_events add column if not exists message text not null default '';
alter table public.agent_events add column if not exists subject jsonb not null default '{}'::jsonb;
alter table public.agent_events add column if not exists job_id text;
alter table public.agent_events add column if not exists brand_id uuid;
alter table public.agent_events add column if not exists account_id uuid;
alter table public.agent_events add column if not exists cost_cents int not null default 0;
alter table public.agent_events add column if not exists data jsonb not null default '{}'::jsonb;
alter table public.agent_events add column if not exists item_id uuid;
alter table public.agent_events add column if not exists user_id uuid;
alter table public.agent_events add column if not exists created_at timestamptz not null default now();

-- ======================================================
-- STEP 4: Drop any bad v5.2 index, then (re)create all
--         indexes with plain btree (no STABLE functions).
-- ======================================================
drop index if exists public.jobs_scheduled;
drop index if exists public.ledger_day;

create index if not exists jobs_status_priority on public.jobs (status, priority desc, created_at);
create index if not exists jobs_scheduled     on public.jobs (scheduled_for);
create index if not exists jobs_type_status   on public.jobs (job_type, status);
create index if not exists jobs_worker        on public.jobs (worker_id, status);
create index if not exists jobs_idempotency   on public.jobs (idempotency_key);
create index if not exists jobs_account       on public.jobs (account_id, created_at desc);

create index if not exists agent_events_tenant_ts on public.agent_events (tenant_id, ts desc);
create index if not exists agent_events_item      on public.agent_events (item_id, ts desc);
create index if not exists agent_events_emitter   on public.agent_events (emitter, ts desc);
create index if not exists agent_events_job       on public.agent_events (job_id, ts desc);

create index if not exists memory_account   on public.memory (account_id, created_at desc);
create index if not exists lessons_scope    on public.lessons (scope, topic, confidence desc);
create index if not exists experiments_account on public.experiments (account_id, created_at desc);
create index if not exists escalations_open on public.escalations (resolved_at, created_at desc);
create index if not exists kpi_metric_ts    on public.kpi_snapshots (metric, ts desc);
create index if not exists trends_niche_heat on public.trend_items (niche, heat desc);

-- ======================================================
-- STEP 5: Legacy table widening (board_items, run_ledger,
--         project_accounts, experiments). These tables
--         already exist from v1-v4 so ALTER is safe.
-- ======================================================

-- settings (safe if already has updated_at)
alter table public.settings add column if not exists updated_at timestamptz not null default now();
alter table public.board_items drop constraint if exists board_items_status_check;
alter table public.board_items add constraint board_items_status_check
    check (status in (
      'idea','drafted','approved','rejected','scheduled',
      'published','reported','failed','cleared','awaiting_approval',
      'archived','queued','drafting','rendering','grading','paused'));
alter table public.board_items add column if not exists account_id uuid;
alter table public.board_items add column if not exists scheduled_at timestamptz;
create index if not exists board_account_status on public.board_items (account_id, status);

alter table public.run_ledger add column if not exists job_id text;
alter table public.run_ledger add column if not exists account_id uuid;
alter table public.run_ledger add column if not exists provider_label text;
alter table public.run_ledger add column if not exists cost_cents int not null default 0;
create index if not exists ledger_job on public.run_ledger (job_id);
create index if not exists ledger_provider on public.run_ledger (provider_label, created_at desc);
create index if not exists ledger_day on public.run_ledger (tenant_id, created_at desc);

alter table public.project_accounts add column if not exists brand_bible jsonb;
alter table public.project_accounts add column if not exists posts_per_day int not null default 2;
alter table public.project_accounts add column if not exists daily_budget_usd numeric(10,2);
alter table public.project_accounts add column if not exists paused boolean not null default false;
alter table public.project_accounts add column if not exists affiliate_urls jsonb not null default '[]'::jsonb;
alter table public.project_accounts add column if not exists sponsor text;

alter table public.experiments drop constraint if exists experiments_status_check;
alter table public.experiments add constraint experiments_status_check
    check (status in ('running','decided','abandoned'));

-- ======================================================
-- STEP 6: RLS off for service-role-only tables
-- ======================================================
alter table public.jobs              disable row level security;
alter table public.memory            disable row level security;
alter table public.lessons           disable row level security;
alter table public.experiments       disable row level security;
alter table public.escalations       disable row level security;
alter table public.worker_health     disable row level security;
alter table public.kpi_snapshots     disable row level security;
alter table public.trend_items       disable row level security;
alter table public.account_documents disable row level security;

-- ======================================================
-- STEP 7: Settings defaults (v5.4: per-category model selection added)
-- ======================================================
insert into public.settings (tenant_id, key, value) values
    ('me', 'kill_switch',  '{"on":false}'::jsonb),
    ('me', 'daily_budget', '{"usd":1.50}'::jsonb),
    ('me', 'autothrottle', '{"on":true,"reserve_fraction":0.1}'::jsonb),
    ('me', 'model',        '{"provider":"anthropic","auto_fallback":true}'::jsonb),
    ('me', 'model_t2i',    '{"model":"gemini-2.5-flash-image"}'::jsonb),
    ('me', 'model_ie',     '{"model":"gemini-image-edit"}'::jsonb),
    ('me', 'model_t2v',    '{"model":"minimax-hailuo-fal"}'::jsonb),
    ('me', 'model_i2v',    '{"model":"minimax-i2v-fal"}'::jsonb),
    ('me', 'model_tts',    '{"model":"eleven-turbo"}'::jsonb),
    ('me', 'model_vedit',  '{"model":"auto-captions-local"}'::jsonb)
on conflict (tenant_id, key) do nothing;

-- Bump schema version to 5.4 so dashboard knows new features are live
insert into public.settings (tenant_id, key, value) values
    ('me', 'schema_version', jsonb_build_object('v','5.4','applied_at_epoch',extract(epoch from now())))
on conflict (tenant_id, key) do update set value = excluded.value;

-- ======================================================
-- STEP 8: REPAIR stuck state from prior crashed runs
-- ======================================================
-- Dead claimed/in_progress jobs (over 1h old) → back to queued
update public.jobs set status='queued', error=null, worker_id=null, claimed_at=null
 where status in ('claimed','in_progress')
   and (coalesce(claimed_at, extract(epoch from now())-7200)) < extract(epoch from now()) - 3600;

-- Queued jobs that already used all attempts → failed
update public.jobs set status='failed'
 where status='queued' and attempts >= max_attempts;

-- Old drafted/scheduled board items with no video → back to idea so v5 can retry cleanly
update public.board_items set status='idea', payload=payload - 'video_path' - 'script' - 'grade'
 where status in ('drafted','scheduled')
   and not (payload ? 'video_path');

-- v5.4 FIX: un-reject items auto-rejected while paused (the bug where 'Stop work'
-- rejected 80+ ideas). Heuristic: rejected items with NO human-entered rejection
-- reason are almost certainly auto-rejects from the bug. Send them back to 'idea'
-- so the new niche-aware worker can process them correctly with right hashtags.
update public.board_items
   set status='idea',
       payload = payload - 'rejection' - 'graded_fail'
 where status='rejected'
   and (payload is null
        or not (payload ? 'rejection')
        or coalesce(payload->'rejection'->>'reason','') in ('','auto','grade_fail','paused')
        or (payload->>'_auto_rejected_while_paused')::boolean is true);

-- Also wipe any stale grades/scripts from the idea pool so the niche-aware
-- brain starts fresh (no more #ai on cat posts from old stale payloads).
update public.board_items
   set payload = payload - 'grade' - 'video_path' - 'visual_path'
 where status='idea'
   and ((payload ? 'script') or (payload ? 'grade'))
   and (payload->'script'->'hashtags')::text like '%ai%';

-- ======================================================
-- STEP 9: Business-plan view for the /b/[aid] web page
-- ======================================================
create or replace view public.v_account_brief as
  select a.id as account_id, a.project_id, a.name, a.handle, a.niche, a.paused,
         a.posts_per_day, a.daily_budget_usd,
         (select content from public.account_documents d
            where d.account_id = a.id and d.doc_type='executive_summary' limit 1) as executive_summary,
         (select content from public.account_documents d
            where d.account_id = a.id and d.doc_type='brand_identity' limit 1) as brand_identity,
         (select content from public.account_documents d
            where d.account_id = a.id and d.doc_type='tone_guide' limit 1) as tone_guide,
         (select content from public.account_documents d
            where d.account_id = a.id and d.doc_type='visual_identity' limit 1) as visual_identity,
         (select content from public.account_documents d
            where d.account_id = a.id and d.doc_type='content_rules' limit 1) as content_rules,
         (select count(*) from public.account_documents d where d.account_id=a.id) as docs_count
  from public.project_accounts a;

-- ======================================================
-- VERIFY (run this yourself after):
--   select value from settings where key='schema_version';
-- Expect: {"v": "5.3", "applied_at_epoch": ...}
-- ======================================================
