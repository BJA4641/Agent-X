-- ============================================================
-- Agent-X v4 QUALITY GATE — grades, memory, pause/resume, chat
-- Run ONCE in Supabase SQL Editor (idempotent).
-- ============================================================

-- 1) PAUSE/RESUME on projects and accounts
alter table public.projects add column if not exists paused boolean not null default false;
alter table public.projects add column if not exists daily_budget_usd numeric(10,2) not null default 2.00;
-- project_accounts already got these columns in v3_upgrade — ensure they exist
alter table public.project_accounts add column if not exists paused boolean not null default false;
alter table public.project_accounts add column if not exists daily_budget_usd numeric(10,2) not null default 0.50;
alter table public.project_accounts add column if not exists posts_per_day int not null default 1;
alter table public.project_accounts add column if not exists config jsonb not null default '{}'::jsonb;

-- 2) MEMORY (chat + instructions + feedback for each account/project)
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

-- 3) CONTENT GRADES — per-piece scorecard
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
    (post_id is not null and exists (select 1 from public.account_posts p join public.project_accounts a on a.id=p.account_id where p.id=content_grades.post_id and a.user_id=auth.uid()))
    or (item_id is not null)  -- board items are tenant-wide (admin view)
  );

-- 4) Add status 'grading' + 'rejected_seed' to board flow
-- We don't alter enum; instead use payload.grade_status field.
-- A post flagged failed by grader gets status=rejected with reason in payload.

select 'v4 quality gate applied' as status;
