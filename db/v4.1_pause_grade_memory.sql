-- ============================================================
-- Agent-X v4.1 — pause/resume enforcement, memory chat, grades
-- Run ONCE in Supabase SQL Editor (idempotent — safe to re-run).
-- Adds missing columns + relaxes trend_items for pattern seeding.
-- ============================================================

-- 1) Ensure pause/budget columns exist on projects + project_accounts
alter table public.projects add column if not exists paused boolean not null default false;
alter table public.projects add column if not exists daily_budget_usd numeric(10,2) not null default 2.00;
alter table public.project_accounts add column if not exists paused boolean not null default false;
alter table public.project_accounts add column if not exists daily_budget_usd numeric(10,2) not null default 0.50;
alter table public.project_accounts add column if not exists posts_per_day int not null default 1;
alter table public.project_accounts add column if not exists platforms_config jsonb not null default '{}'::jsonb;
alter table public.project_accounts add column if not exists config jsonb not null default '{}'::jsonb;

-- 2) Ensure avatar_emoji column exists (for accounts page rendering)
alter table public.project_accounts add column if not exists avatar_emoji text not null default '🤖';

-- 3) MEMORY table
create table if not exists public.memory_entries (
  id bigint generated always as identity primary key,
  tenant_id text not null default 'me',
  project_id uuid references public.projects(id) on delete cascade,
  account_id uuid references public.project_accounts(id) on delete cascade,
  role text not null check (role in ('user','architect','strategist','brain','qa','grader','visuals','system')),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists memory_account_idx on public.memory_entries(account_id, created_at desc);
create index if not exists memory_project_idx on public.memory_entries(project_id, created_at desc);
alter table public.memory_entries enable row level security;
drop policy if exists "own memory" on public.memory_entries;
create policy "own memory" on public.memory_entries for all
  using (
    (account_id is not null and exists (select 1 from public.project_accounts a where a.id = account_id and a.user_id = auth.uid()))
    or
    (project_id is not null and exists (select 1 from public.projects p where p.id = project_id and p.user_id = auth.uid()))
  )
  with check (
    (account_id is not null and exists (select 1 from public.project_accounts a where a.id = account_id and a.user_id = auth.uid()))
    or
    (project_id is not null and exists (select 1 from public.projects p where p.id = project_id and p.user_id = auth.uid()))
  );

-- 4) CONTENT GRADES table
create table if not exists public.content_grades (
  id bigint generated always as identity primary key,
  tenant_id text not null default 'me',
  post_id uuid references public.account_posts(id) on delete cascade,
  item_id uuid references public.board_items(id) on delete cascade,
  grader text not null default 'grader',
  hook int not null check (hook between 1 and 10),
  visuals int not null check (visuals between 1 and 10),
  pacing int not null check (pacing between 1 and 10),
  audio int not null check (audio between 1 and 10),
  caption int not null check (caption between 1 and 10),
  cta int not null check (cta between 1 and 10),
  overall numeric(3,1) not null,
  passed boolean not null default false,
  notes text,
  fix_instruction text,
  created_at timestamptz not null default now()
);
create index if not exists grades_post_idx on public.content_grades(post_id, created_at desc);
create index if not exists grades_item_idx on public.content_grades(item_id, created_at desc);
alter table public.content_grades enable row level security;
drop policy if exists "own grades" on public.content_grades;
create policy "own grades" on public.content_grades for select
  using (
    (post_id is not null and exists (
      select 1 from public.account_posts p join public.project_accounts a on a.id=p.account_id
      where p.id=content_grades.post_id and a.user_id=auth.uid()
    ))
    or (item_id is not null)
  );
-- Grade INSERT policy: the service role (pipeline) does inserts; user has no direct insert.
drop policy if exists "service inserts grades" on public.content_grades;
create policy "service inserts grades" on public.content_grades for insert
  with check (true);

-- 5) Ensure agent_events RLS lets us see system events (null user_id for pipeline events)
drop policy if exists "agent events read" on public.agent_events;
create policy "agent events read" on public.agent_events for select
  using (user_id = auth.uid() or user_id is null);

-- 6) account_posts — ensure grade-related columns/columns the UI needs exist
alter table public.account_posts add column if not exists hook text;
alter table public.account_posts add column if not exists script text;
alter table public.account_posts add column if not exists caption text;
alter table public.account_posts add column if not exists visual_prompt text;
alter table public.account_posts add column if not exists duration_seconds int not null default 30;
alter table public.account_posts add column if not exists created_by_agent text not null default 'strategist';
alter table public.account_posts add column if not exists metadata jsonb not null default '{}'::jsonb;

-- 7) project_accounts status enum — add 'paused' as accepted (status is text, so just a safety check)
--    (status is plain text in our schema, not enum, so no alteration needed.)

-- 8) Helpful indexes
create index if not exists accounts_project_idx on public.project_accounts(project_id, status);
create index if not exists accounts_ready_idx on public.project_accounts(status, paused);
create index if not exists posts_account_status_idx on public.account_posts(account_id, status, created_at);

select 'v4.1 pause/grade/memory applied' as status;
