-- ============================================================
-- BuildAlong — SINGLE canonical schema (board + web + ledger)
-- Run once in Supabase → SQL editor. Multi-tenant via RLS.
-- ============================================================

-- ---------- CONTENT BOARD (the state machine) ----------
create table if not exists board_items (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   text not null default 'me',
  status      text not null default 'idea'
              check (status in ('idea','drafted','approved','rejected','scheduled','published','reported','failed')),
  topic       text not null,
  payload     jsonb not null default '{}'::jsonb,   -- state contracts live here (script, media, receipts)
  scheduled_at timestamptz,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists board_tenant_status on board_items (tenant_id, status);

-- ---------- RUN LEDGER (cost metering; future SaaS billing) ----------
create table if not exists run_ledger (
  id          bigint generated always as identity primary key,
  tenant_id   text not null default 'me',
  item_id     uuid references board_items(id),
  step        text not null,            -- brain | visuals | voice | publish_ig | publish_yt | strategy
  model       text,
  prompt_version text,
  cost_usd    numeric(10,5) not null default 0,
  ok          boolean not null default true,
  detail      text,
  created_at  timestamptz not null default now()
);
create index if not exists ledger_tenant_day on run_ledger (tenant_id, created_at);

-- ---------- PERFORMANCE (feeds Strategy) ----------
create table if not exists performance (
  id          bigint generated always as identity primary key,
  tenant_id   text not null default 'me',
  item_id     uuid references board_items(id),
  platform    text not null,
  views       int default 0, likes int default 0, comments int default 0,
  captured_at timestamptz not null default now()
);

-- ---------- WEB: entitlements, progress, waitlist ----------
create table if not exists entitlements (
  user_id     uuid not null references auth.users(id) on delete cascade,
  module_id   text not null,
  stripe_session text,
  created_at  timestamptz not null default now(),
  primary key (user_id, module_id)
);
create table if not exists task_progress (
  user_id     uuid not null references auth.users(id) on delete cascade,
  task_key    text not null,
  done        boolean not null default false,
  proof       jsonb,
  updated_at  timestamptz not null default now(),
  primary key (user_id, task_key)
);
create table if not exists waitlist (
  email       text primary key,
  note        text,
  created_at  timestamptz not null default now()
);

-- ---------- RLS ----------
alter table board_items  enable row level security;
alter table run_ledger   enable row level security;
alter table performance  enable row level security;
alter table entitlements enable row level security;
alter table task_progress enable row level security;
alter table waitlist     enable row level security;

-- Web users only ever see their own rows:
create policy "own entitlements" on entitlements for select using (auth.uid() = user_id);
create policy "own progress"     on task_progress for all   using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- Waitlist: anyone may insert, nobody may read (service role bypasses RLS):
create policy "waitlist insert"  on waitlist for insert with check (true);
-- Board/ledger/performance: NO user policies on purpose — the pipeline worker
-- uses the service-role key (bypasses RLS). Tenant dashboards get policies in Phase B.

-- ---------- SETTINGS (remote control: kill switch etc.) ----------
create table if not exists settings (
  tenant_id  text not null default 'me',
  key        text not null,
  value      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, key)
);
alter table settings enable row level security;  -- service-role only, like the board

-- safe on re-run / existing deploys:
alter table task_progress add column if not exists proof jsonb;
