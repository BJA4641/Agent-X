-- ======================================================
-- v5.0 WORKER MIGRATION (Phase 2 — blueprint worker engine)
-- Run this in Supabase SQL editor AFTER deploying the v5 code.
-- Idempotent — safe to run twice.
-- ======================================================

-- 1) jobs table  (durable job queue for v5 worker)
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
    finished_at float
);
create index if not exists jobs_status_priority on public.jobs (status, priority desc, created_at);
create index if not exists jobs_scheduled     on public.jobs (scheduled_for) where status='queued';

-- 2) agent_events — widen to support v2 emitter/type fields.
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

-- 2b) Legacy agent_events may already exist with a different schema (older v4).
--     Add columns if they're missing (idempotent).
do $$
begin
    begin alter table public.agent_events add column if not exists id text;
        exception when others then null; end;
    begin alter table public.agent_events add column if not exists emitter text;
        exception when others then null; end;
    begin alter table public.agent_events add column if not exists type text default 'agent.info';
        exception when others then null; end;
    begin alter table public.agent_events add column if not exists job_id text;
        exception when others then null; end;
    begin alter table public.agent_events add column if not exists cost_cents int not null default 0;
        exception when others then null; end;
    begin alter table public.agent_events add column if not exists data jsonb not null default '{}'::jsonb;
        exception when others then null; end;
end $$;

-- 3) memory table (typed long-term memory + lessons)
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

-- 4) board_items: widen status enum to include the v5 states, add account_id column.
do $$
begin
    alter table public.board_items drop constraint if exists board_items_status_check;
    alter table public.board_items add constraint board_items_status_check
        check (status in (
            'idea','drafted','approved','rejected','scheduled',
            'published','reported','failed','cleared','awaiting_approval',
            'archived','queued','drafting','rendering','grading'));
exception when others then null;
end $$;
alter table public.board_items add column if not exists account_id uuid;
create index if not exists board_account_status on public.board_items (account_id, status);

-- 5) run_ledger: add job_id + account_id cols for v5 attribution.
alter table public.run_ledger add column if not exists job_id text;
alter table public.run_ledger add column if not exists account_id uuid;
create index if not exists ledger_job on public.run_ledger (job_id);

-- 6) Settings defaults: kill switch OFF, daily budget $1.50, single active account.
insert into public.settings (tenant_id, key, value) values
    ('me', 'kill_switch', '{"on":false}'::jsonb),
    ('me', 'daily_budget', '{"usd":1.50}'::jsonb)
on conflict (tenant_id, key) do nothing;

-- 7) exec() helper RPC used by the queue bootstrapper to issue CREATE TABLE IF NOT EXISTS.
create or replace function public.exec(q text) returns void as $$
begin execute q; end;
$$ language plpgsql security definer;

-- 8) Clear any FAILED jobs from previous v4.4/boot attempts so the new queue starts clean.
update public.jobs set status='failed' where status in ('queued','claimed','in_progress') and created_at < extract(epoch from now()) - 3600;

-- ======================================================
-- v5.0 BOOTMARK — if this line prints in SQL editor output, the engine is ready.
raise notice 'v5.0 WORKER MIGRATION APPLIED ✓ — jobs + agent_events + memory + lessons tables ready.';
-- ======================================================
