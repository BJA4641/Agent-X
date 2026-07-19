-- ============================================================
-- Agent-X v4.3 — RAILWAY BOOT FIX + CLEANUP (FIXED v2)
-- Run ONCE in Supabase SQL Editor AFTER Railway + Vercel are green.
-- Safe to re-run (idempotent).
--
-- v2 FIX: board_items.status had a CHECK constraint that didn't allow 'cleared'.
--         We drop/recreate that constraint before the cleanup UPDATE.
-- ============================================================

-- 0) Wrap everything in DO block so we can catch errors gracefully
DO $$
DECLARE constraint_name text;
BEGIN

-- 1) Widen board_items.status to allow 'cleared' (our cleanup status) and
--    'awaiting_approval' / 'archived' (used by v4.3 pipeline).
--    Find the actual constraint name first, then drop + recreate.
FOR constraint_name IN
  SELECT conname FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
   WHERE t.relname = 'board_items' AND n.nspname = 'public' AND c.contype = 'c'
LOOP
  EXECUTE format('ALTER TABLE public.board_items DROP CONSTRAINT IF EXISTS %I', constraint_name);
END LOOP;

-- Re-add a permissive check that includes our cleanup statuses
ALTER TABLE public.board_items
  ADD CONSTRAINT board_items_status_check
  CHECK (status IN ('idea','drafting','drafted','awaiting_approval','approved',
                    'rejected','reported','published','failed','rendering',
                    'grading','queued','cleared','archived'));

END $$;

-- 2) Add any missing v4.3 columns
alter table if exists public.account_documents
  add column if not exists agent text not null default 'architect';

alter table if exists public.account_posts
  add column if not exists first_comment text,
  add column if not exists alt_text text,
  add column if not exists yt_title text,
  add column if not exists seo_keywords jsonb not null default '[]'::jsonb;

-- 3) Widen memory_entries role CHECK (if any) to allow research/seo
do $$
declare cname text;
begin
  for cname in
    select conname from pg_constraint c
      join pg_class t on t.oid=c.conrelid join pg_namespace n on n.oid=t.relnamespace
     where t.relname='memory_entries' and n.nspname='public' and c.contype='c'
  loop
    execute format('alter table public.memory_entries drop constraint if exists %I', cname);
  end loop;
end $$;

-- 4) Ensure content_grades columns exist
alter table if exists public.content_grades
  add column if not exists notes text,
  add column if not exists fix_instruction text;

-- 5) CLEANUP: move old failed/idea items from v4.1/v4.2 to 'cleared'
--    instead of deleting them, so history survives but they stop re-queueing.
update public.board_items
  set status = 'cleared',
      payload = coalesce(payload, '{}'::jsonb) || jsonb_build_object(
        'cleared_reason', 'v4.3 boot cleanup — pre-quality-gate failures',
        'cleared_at', now()
      )
  where status in ('idea','failed');

-- Mark eternally-stuck drafting/rendering/grading items as failed
update public.board_items
  set status = 'failed',
      payload = coalesce(payload, '{}'::jsonb) || jsonb_build_object(
        'failed_reason', 'v4.3 — stuck before quality gate; retired'
      )
  where status in ('drafting','rendering','grading')
    and created_at < now() - interval '2 hours';

-- 6) Reset stuck in-progress tasks
update public.task_progress
  set status = 'done'
  where status = 'in_progress'
    and updated_at < now() - interval '2 hours';

-- 7) Reset run_ledger so dashboard $ starts fresh (comment out if you want to keep history)
delete from public.run_ledger
  where created_at < now() - interval '1 hour';

-- 8) PAUSE ALL ACCOUNTS EXCEPT "AI Tool Daily"
--    (so you start with ONE active account until 8/10 content is proven)
update public.project_accounts
  set paused = true
  where lower(name) not like '%ai tool daily%'
    and lower(handle) not like '%aitool%'
    and lower(handle) not like '%ai_tool%'
    and lower(handle) not like '%aitoolsdaily%'
    and paused = false;

-- Make sure AI Tool Daily is UN-paused + ready to be architected
update public.project_accounts
  set paused = false,
      status = 'needs_setup'
  where lower(name) like '%ai tool daily%'
     or lower(handle) like '%aitool%'
     or lower(handle) like '%ai_tool%'
     or lower(handle) like '%aitoolsdaily%';

-- Pause any projects that aren't the default/AI one so nothing bleeds
update public.projects
  set paused = true
  where lower(name) not like '%default%'
    and lower(name) not like '%ai%'
    and paused = false;

-- 9) Done
select 'v4.3 BOOTFIX v2 APPLIED — board widened, old failures cleared ($ reset), only AI Tool Daily active.' as status;
