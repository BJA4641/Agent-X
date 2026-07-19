-- ============================================================
-- ACTIVATE AGENTS — run this ONCE in Supabase SQL Editor.
-- Fixes RLS so the website can SEE system events written by
-- the Railway pipeline (which inserts with user_id = NULL).
-- Safe to re-run.
-- ============================================================

-- 1) Make sure the table + columns exist (idempotent)
create table if not exists agent_events (
  id bigint generated always as identity primary key,
  tenant_id text not null default 'me',
  user_id uuid references auth.users(id) on delete cascade,
  agent text not null default 'system',
  action text not null default 'note',
  item_id uuid references board_items(id) on delete set null,
  message text,
  status text not null default 'info',
  cost_usd numeric(10,5) not null default 0,
  created_at timestamptz not null default now()
);

do $$ begin
  alter table agent_events add constraint ae_status_check
    check (status in ('info','success','warn','error','debate'));
exception when others then null; end $$;

create index if not exists ae_tenant_ts on agent_events(tenant_id, created_at desc);
create index if not exists ae_user_ts   on agent_events(user_id,   created_at desc);

-- 2) ENABLE RLS + FIX POLICIES so system-wide (user_id NULL) events are visible
do $$ begin alter table agent_events enable row level security; exception when others then null; end $$;

drop policy if exists "own events" on agent_events;
create policy "own events" on agent_events for select
  using (auth.uid() = user_id or (user_id is null and tenant_id = 'me'));

drop policy if exists "insert events" on agent_events;
create policy "insert events" on agent_events for insert
  with check (auth.uid() = user_id or user_id is null);

-- 3) Optional: wipe stale demo-only events from before the real pipeline started
-- (commented out for safety — uncomment if you want a clean feed)
-- delete from agent_events where agent = 'system' and action = 'seed';

-- 4) Seed one boot event now so the workspace feed lights up immediately,
--    even before the Railway worker re-deploys.
insert into agent_events (tenant_id, user_id, agent, action, message, status, cost_usd)
values
  ('me', null, 'system',   'manual_seed', 'Activate-Agents SQL applied. Waiting for Railway worker to boot (usually 1-2 min after redeploy)…', 'success', 0),
  ('me', null, 'strategy', 'manual_seed', 'Standing by — I will scan trends and plan topics on the next tick.', 'info', 0),
  ('me', null, 'brain',    'manual_seed', 'Pen is up. Ready to write scripts.', 'info', 0),
  ('me', null, 'visuals',  'manual_seed', 'Gemini is loaded. Beat frames ready on demand.', 'info', 0),
  ('me', null, 'voice',    'manual_seed', 'Voice profiles tuned.', 'info', 0),
  ('me', null, 'qa',       'manual_seed', 'Retention + claim checklists hot.', 'info', 0),
  ('me', null, 'publisher','manual_seed', 'Calendar slots open.', 'info', 0),
  ('me', null, 'budget',   'manual_seed', 'Budget guard armed — will not overspend.', 'success', 0);

-- 5) Verify
select count(*) as total_events,
       count(*) filter (where user_id is null) as system_events,
       count(*) filter (where status='error') as errors
from agent_events;
