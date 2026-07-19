-- ======================================================
-- v5.1 PRODUCTION MIGRATION (Phase 3 — Optimization)
-- Run this in Supabase SQL editor AFTER deploying v5.0 code.
-- Idempotent — safe to run twice. NO procedural DO/raise blocks.
-- ======================================================
-- (If v5.0 migration did not apply cleanly, this file is a
-- SUPERSET that creates/updates everything v5.0 needed.)
-- ======================================================

-- 1) jobs table (durable job queue)
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
create index if not exists jobs_status_priority on public.jobs (status, priority desc, created_at);
create index if not exists jobs_scheduled     on public.jobs (scheduled_for) where status='queued';
create index if not exists jobs_type_status   on public.jobs (job_type, status);
create index if not exists jobs_worker        on public.jobs (worker_id, status);

-- 2) agent_events v2 — widened schema for v5 worker
create table if not exists public.agent_events (
    id text primary key default substr(md5(random()::text || clock_timestamp()::text),1,12),
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
create index if not exists agent_events_tenant_ts on public.agent_events (tenant_id, ts desc);
create index if not exists agent_events_item      on public.agent_events (item_id, ts desc);
create index if not exists agent_events_emitter   on public.agent_events (emitter, ts desc);

-- Backfill missing columns on pre-v5 agent_events tables
alter table public.agent_events add column if not exists id text;
alter table public.agent_events add column if not exists emitter text;
alter table public.agent_events add column if not exists type text default 'agent.info';
alter table public.agent_events add column if not exists job_id text;
alter table public.agent_events add column if not exists cost_cents int not null default 0;
alter table public.agent_events add column if not exists data jsonb not null default '{}'::jsonb;

-- 3) memory + lessons (self-improvement)
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
create index if not exists lessons_scope on public.lessons (scope, topic, confidence desc);

-- 4) board_items: widen status enum + account_id column
alter table public.board_items drop constraint if exists board_items_status_check;
alter table public.board_items add constraint board_items_status_check
    check (status in (
        'idea','drafted','approved','rejected','scheduled',
        'published','reported','failed','cleared','awaiting_approval',
        'archived','queued','drafting','rendering','grading'));
alter table public.board_items add column if not exists account_id uuid;
create index if not exists board_account_status on public.board_items (account_id, status);
-- scheduled_at may not exist on older deploys
alter table public.board_items add column if not exists scheduled_at timestamptz;

-- 5) run_ledger: add job_id + account_id for v5 attribution
alter table public.run_ledger add column if not exists job_id text;
alter table public.run_ledger add column if not exists account_id uuid;
create index if not exists ledger_job     on public.run_ledger (job_id);
create index if not exists ledger_day     on public.run_ledger (tenant_id, date_trunc('day', created_at));

-- 6) project_accounts: add brand_bible jsonb column (Phase 1 BrandBible schema)
alter table public.project_accounts add column if not exists brand_bible jsonb;
alter table public.project_accounts add column if not exists posts_per_day int not null default 2;
alter table public.project_accounts add column if not exists daily_budget_usd numeric(10,2);

-- 7) experiments (A/B hook/title/thumbnail trials for self-improvement loop)
create table if not exists public.experiments (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    account_id uuid,
    item_id uuid references board_items(id) on delete set null,
    topic text not null,
    variants jsonb not null,            -- [{name:'A', hook:'...', prompt:'...'}, ...]
    winner text,                        -- variant name chosen
    winning_reason text,
    status text not null default 'running' check (status in ('running','decided','abandoned')),
    decision_at timestamptz,
    created_at timestamptz not null default now()
);
create index if not exists experiments_account on public.experiments (account_id, created_at desc);

-- 8) escalations (human-desk queue for CEO/founder approvals)
create table if not exists public.escalations (
    id uuid primary key default gen_random_uuid(),
    tenant_id text not null default 'me',
    job_id text,
    item_id uuid references board_items(id) on delete set null,
    account_id uuid,
    severity text not null default 'ask',     -- ask | warn | kill
    summary text not null,
    options jsonb not null default '[]'::jsonb,
    context jsonb not null default '{}'::jsonb,
    resolution text,                          -- 'approve' | 'reject' | custom
    resolved_by uuid references auth.users(id) on delete set null,
    resolved_note text,
    created_at timestamptz not null default now(),
    resolved_at timestamptz,
    deadline_hours float not null default 24
);
create index if not exists escalations_open on public.escalations (resolved_at, created_at desc);

-- 9) worker_health (heartbeat rows so the dashboard shows worker status)
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

-- 10) kpi_snapshots (hourly rollups for CEO dashboard)
create table if not exists public.kpi_snapshots (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me',
    ts timestamptz not null default now(),
    metric text not null,         -- 'spend_usd' | 'publishes' | 'views' | 'engagement' | 'inflight'
    value numeric(14,4) not null default 0,
    dimensions jsonb not null default '{}'::jsonb
);
create index if not exists kpi_metric_ts on public.kpi_snapshots (metric, ts desc);

-- 11) Settings defaults (kill switch OFF, budget $1.50)
insert into public.settings (tenant_id, key, value) values
    ('me', 'kill_switch', '{"on":false}'::jsonb),
    ('me', 'daily_budget', '{"usd":1.50}'::jsonb),
    ('me', 'autothrottle', '{"on":true,"reserve_fraction":0.1}'::jsonb)
on conflict (tenant_id, key) do nothing;

-- 12) RLS for new tables: same model as board_items/run_ledger (service role only;
--     web users read via admin endpoints, not directly).
alter table public.jobs           disable row level security;
alter table public.memory         disable row level security;
alter table public.lessons        disable row level security;
alter table public.experiments    disable row level security;
alter table public.escalations    disable row level security;
alter table public.worker_health  disable row level security;
alter table public.kpi_snapshots  disable row level security;
-- agent_events RLS is already the default (no policies = owner-only in prod);
-- the service key bypasses RLS, which is what the web API uses.

-- 13) Bootstrap marker: insert a boot row into settings so future SQL can
--     detect which migrations are applied.
insert into public.settings (tenant_id, key, value) values
    ('me', 'schema_version', '{"v":5.1,"applied_at_epoch":'||extract(epoch from now())||'}'::jsonb)
on conflict (tenant_id, key) do update set value = excluded.value;

-- ======================================================
-- v5.1 PRODUCTION MIGRATION APPLIED.
-- Confirm by checking settings: select * from settings where key='schema_version';
-- You should see {"v": 5.1, "applied_at_epoch": ...}.
-- ======================================================
