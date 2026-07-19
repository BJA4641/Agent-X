-- ======================================================
-- v5.2 PRODUCTION MIGRATION (Phase 3 continued)
-- Run this in Supabase SQL editor. Idempotent — safe to re-run.
-- FIX for v5.1 error "column 'ts' does not exist":
--   We add ALL missing columns FIRST, then create indexes.
-- ======================================================
-- This is a full rebuild-safe migration: covers everything v5.0 + v5.1 added,
-- so you can run this against ANY state (clean DB, v4.x, v5.0 that failed
-- mid-way, v5.1 partial) and end up at v5.2 schema.
-- ======================================================

-- 1) JOBS table (durable job queue)
create table if not exists public.jobs (
    id text primary key,
    job_type text not null,
    brand_id uuid,
    account_id uuid,
    project_id uuid,
    priority int not null default 50,
    status text not null default 'queued'
        check (status in ('queued','claimed','in_progress','wait_human','done','failed','blocked')),
    payload jsonb not null default '{}'::jsonb,
    result jsonb,
    attempts int not null default 0,
    max_attempts int not null default 2,
    parent_job_id text,
    requested_by text not null default 'system',
    worker_id text,
    scheduled_for float not null default extract(epoch from now()),
    deadline float,
    error text,
    cost_cents int not null default 0,
    idempotency_key text unique,
    created_at float not null default extract(epoch from now()),
    claimed_at float,
    finished_at float,
    started_at float,
    last_heartbeat_at float
);
-- Jobs indexes
create index if not exists jobs_status_priority on public.jobs (status, priority desc, created_at);
create index if not exists jobs_scheduled     on public.jobs (scheduled_for) where status='queued';
create index if not exists jobs_type_status   on public.jobs (job_type, status);
create index if not exists jobs_worker        on public.jobs (worker_id, status);
create index if not exists jobs_idempotency   on public.jobs (idempotency_key);
-- Jobs: backfill any missing columns (in case the table was created by a broken v5.0)
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
-- Re-apply status check (drop old one first, recreate)
alter table public.jobs drop constraint if exists jobs_status_check;
alter table public.jobs add  constraint jobs_status_check
    check (status in ('queued','claimed','in_progress','wait_human','done','failed','blocked'));


-- 2) AGENT_EVENTS — FIRST add every column the v5 schema needs (this is what
--    fixes the "column ts does not exist" error if legacy table existed),
--    THEN create the table if missing (on a clean DB), THEN create indexes.
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

create table if not exists public.agent_events (
    id text,
    tenant_id text not null default 'me',
    ts float not null default extract(epoch from now()),
    emitter text not null,
    type text not null default 'agent.info',
    status text not null default 'info',
    action text not null default '',
    message text not null default '',
    subject jsonb not null default '{}'::jsonb,
    job_id text,
    brand_id uuid,
    account_id uuid,
    cost_cents int not null default 0,
    data jsonb not null default '{}'::jsonb,
    item_id uuid references board_items(id) on delete set null,
    user_id uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now()
);

-- Indexes for agent_events SAFE NOW (columns guaranteed to exist)
create index if not exists agent_events_tenant_ts on public.agent_events (tenant_id, ts desc);
create index if not exists agent_events_item      on public.agent_events (item_id, ts desc);
create index if not exists agent_events_emitter   on public.agent_events (emitter, ts desc);
create index if not exists agent_events_job       on public.agent_events (job_id, ts desc);


-- 3) MEMORY + LESSONS
create table if not exists public.memory (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    account_id uuid,
    project_id uuid,
    brand_id uuid,
    role text not null,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
alter table public.memory add column if not exists tenant_id text not null default 'me';
alter table public.memory add column if not exists account_id uuid;
alter table public.memory add column if not exists project_id uuid;
alter table public.memory add column if not exists brand_id uuid;
alter table public.memory add column if not exists role text not null default 'system';
alter table public.memory add column if not exists content text not null default '';
alter table public.memory add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.memory add column if not exists created_at timestamptz not null default now();
create index if not exists memory_account on public.memory (account_id, created_at desc);

create table if not exists public.lessons (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    scope text not null,
    subject_id text,
    topic text not null,
    lesson text not null,
    evidence jsonb not null default '{}'::jsonb,
    confidence float not null default 0.5,
    applied_at timestamptz,
    created_at timestamptz not null default now()
);
alter table public.lessons add column if not exists tenant_id text not null default 'me';
alter table public.lessons add column if not exists scope text not null default 'global';
alter table public.lessons add column if not exists subject_id text;
alter table public.lessons add column if not exists topic text not null default '';
alter table public.lessons add column if not exists lesson text not null default '';
alter table public.lessons add column if not exists evidence jsonb not null default '{}'::jsonb;
alter table public.lessons add column if not exists confidence float not null default 0.5;
alter table public.lessons add column if not exists applied_at timestamptz;
alter table public.lessons add column if not exists created_at timestamptz not null default now();
create index if not exists lessons_scope on public.lessons (scope, topic, confidence desc);


-- 4) BOARD_ITEMS: widen status + add account_id
alter table public.board_items drop constraint if exists board_items_status_check;
alter table public.board_items add constraint board_items_status_check
    check (status in (
        'idea','drafted','approved','rejected','scheduled',
        'published','reported','failed','cleared','awaiting_approval',
        'archived','queued','drafting','rendering','grading'));
alter table public.board_items add column if not exists account_id uuid;
alter table public.board_items add column if not exists scheduled_at timestamptz;
create index if not exists board_account_status on public.board_items (account_id, status);


-- 5) RUN_LEDGER columns
alter table public.run_ledger add column if not exists job_id text;
alter table public.run_ledger add column if not exists account_id uuid;
create index if not exists ledger_job on public.run_ledger (job_id);
create index if not exists ledger_day on public.run_ledger (tenant_id, date_trunc('day', created_at));


-- 6) PROJECT_ACCOUNTS columns
alter table public.project_accounts add column if not exists brand_bible jsonb;
alter table public.project_accounts add column if not exists posts_per_day int not null default 2;
alter table public.project_accounts add column if not exists daily_budget_usd numeric(10,2);
alter table public.project_accounts add column if not exists paused boolean not null default false;


-- 7) EXPERIMENTS (A/B tests)
create table if not exists public.experiments (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    account_id uuid,
    item_id uuid references board_items(id) on delete set null,
    topic text not null,
    variants jsonb not null,
    winner text,
    winning_reason text,
    status text not null default 'running' check (status in ('running','decided','abandoned')),
    decision_at timestamptz,
    created_at timestamptz not null default now()
);
alter table public.experiments add column if not exists tenant_id text not null default 'me';
alter table public.experiments add column if not exists account_id uuid;
alter table public.experiments add column if not exists item_id uuid;
alter table public.experiments add column if not exists topic text not null default '';
alter table public.experiments add column if not exists variants jsonb not null default '[]'::jsonb;
alter table public.experiments add column if not exists winner text;
alter table public.experiments add column if not exists winning_reason text;
alter table public.experiments add column if not exists status text not null default 'running';
alter table public.experiments add column if not exists decision_at timestamptz;
alter table public.experiments add column if not exists created_at timestamptz not null default now();
alter table public.experiments drop constraint if exists experiments_status_check;
alter table public.experiments add constraint experiments_status_check
    check (status in ('running','decided','abandoned'));
create index if not exists experiments_account on public.experiments (account_id, created_at desc);


-- 8) ESCALATIONS (human-desk)
create table if not exists public.escalations (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    job_id text,
    item_id uuid references board_items(id) on delete set null,
    account_id uuid,
    severity text not null default 'ask',
    summary text not null,
    options jsonb not null default '[]'::jsonb,
    context jsonb not null default '{}'::jsonb,
    resolution text,
    resolved_by uuid references auth.users(id) on delete set null,
    resolved_note text,
    created_at timestamptz not null default now(),
    resolved_at timestamptz,
    deadline_hours float not null default 24
);
alter table public.escalations add column if not exists tenant_id text not null default 'me';
alter table public.escalations add column if not exists job_id text;
alter table public.escalations add column if not exists item_id uuid;
alter table public.escalations add column if not exists account_id uuid;
alter table public.escalations add column if not exists severity text not null default 'ask';
alter table public.escalations add column if not exists summary text not null default '';
alter table public.escalations add column if not exists options jsonb not null default '[]'::jsonb;
alter table public.escalations add column if not exists context jsonb not null default '{}'::jsonb;
alter table public.escalations add column if not exists resolution text;
alter table public.escalations add column if not exists resolved_by uuid;
alter table public.escalations add column if not exists resolved_note text;
alter table public.escalations add column if not exists created_at timestamptz not null default now();
alter table public.escalations add column if not exists resolved_at timestamptz;
alter table public.escalations add column if not exists deadline_hours float not null default 24;
create index if not exists escalations_open on public.escalations (resolved_at, created_at desc);


-- 9) WORKER_HEALTH
create table if not exists public.worker_health (
    worker_id text primary key,
    tenant_id text not null default 'me',
    started_at float not null default extract(epoch from now()),
    last_heartbeat_at float not null default extract(epoch from now()),
    jobs_completed int not null default 0,
    jobs_failed int not null default 0,
    jobs_in_progress int not null default 0,
    last_error text,
    host text,
    version text
);
alter table public.worker_health add column if not exists tenant_id text not null default 'me';
alter table public.worker_health add column if not exists started_at float not null default extract(epoch from now());
alter table public.worker_health add column if not exists last_heartbeat_at float not null default extract(epoch from now());
alter table public.worker_health add column if not exists jobs_completed int not null default 0;
alter table public.worker_health add column if not exists jobs_failed int not null default 0;
alter table public.worker_health add column if not exists jobs_in_progress int not null default 0;
alter table public.worker_health add column if not exists last_error text;
alter table public.worker_health add column if not exists host text;
alter table public.worker_health add column if not exists version text;


-- 10) KPI_SNAPSHOTS
create table if not exists public.kpi_snapshots (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me',
    ts timestamptz not null default now(),
    metric text not null,
    value numeric(14,4) not null default 0,
    dimensions jsonb not null default '{}'::jsonb
);
alter table public.kpi_snapshots add column if not exists tenant_id text not null default 'me';
alter table public.kpi_snapshots add column if not exists ts timestamptz not null default now();
alter table public.kpi_snapshots add column if not exists metric text not null default '';
alter table public.kpi_snapshots add column if not exists value numeric(14,4) not null default 0;
alter table public.kpi_snapshots add column if not exists dimensions jsonb not null default '{}'::jsonb;
create index if not exists kpi_metric_ts on public.kpi_snapshots (metric, ts desc);


-- 11) TREND_ITEMS (scout writes here — confirm it exists with expected columns)
create table if not exists public.trend_items (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    title text not null,
    url text,
    platform text,
    niche text,
    heat float not null default 0,
    angle text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
alter table public.trend_items add column if not exists tenant_id text not null default 'me';
alter table public.trend_items add column if not exists title text not null default '';
alter table public.trend_items add column if not exists url text;
alter table public.trend_items add column if not exists platform text;
alter table public.trend_items add column if not exists niche text;
alter table public.trend_items add column if not exists heat float not null default 0;
alter table public.trend_items add column if not exists angle text;
alter table public.trend_items add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.trend_items add column if not exists created_at timestamptz not null default now();
create index if not exists trends_niche_heat on public.trend_items (niche, heat desc);


-- 12) ACCOUNT_DOCUMENTS (Brand Bible per account — architect writes here)
create table if not exists public.account_documents (
    account_id uuid not null,
    doc_type text not null,
    content text not null default '',
    updated_at timestamptz not null default now(),
    primary key (account_id, doc_type)
);
alter table public.account_documents add column if not exists account_id uuid;
alter table public.account_documents add column if not exists doc_type text not null default '';
alter table public.account_documents add column if not exists content text not null default '';
alter table public.account_documents add column if not exists updated_at timestamptz not null default now();


-- 13) SETTINGS defaults (kill switch OFF, budget $1.50, autothrottle ON)
insert into public.settings (tenant_id, key, value) values
    ('me', 'kill_switch',  '{"on":false}'::jsonb),
    ('me', 'daily_budget', '{"usd":1.50}'::jsonb),
    ('me', 'autothrottle', '{"on":true,"reserve_fraction":0.1}'::jsonb),
    ('me', 'model',        '{"provider":"anthropic"}'::jsonb)
on conflict (tenant_id, key) do nothing;

insert into public.settings (tenant_id, key, value) values
    ('me', 'schema_version', '{"v":5.2,"applied_at_epoch":'||extract(epoch from now())||'}'::jsonb)
on conflict (tenant_id, key) do update set value = excluded.value;


-- 14) RLS — service-role only (same policy as board/ledger); web reads via admin APIs.
alter table public.jobs           disable row level security;
alter table public.memory         disable row level security;
alter table public.lessons        disable row level security;
alter table public.experiments    disable row level security;
alter table public.escalations    disable row level security;
alter table public.worker_health  disable row level security;
alter table public.kpi_snapshots  disable row level security;
alter table public.trend_items    disable row level security;
alter table public.account_documents disable row level security;


-- 15) Clear stale in-progress jobs from any failed pre-v5.2 run so they don't stall.
update public.jobs set status='failed', error='cleared by v5.2 migration'
 where status in ('claimed','in_progress') and created_at < extract(epoch from now()) - 3600;

-- ======================================================
-- VERIFY: Run this in Supabase AFTER the migration:
--   select value from settings where key='schema_version';
-- Expect: {"v": 5.2, "applied_at_epoch": ...}
-- ======================================================
