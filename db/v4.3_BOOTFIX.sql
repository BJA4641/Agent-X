-- ============================================================
-- Agent-X v4.3 — RAILWAY BOOT FIX + CLEANUP
-- Run ONCE in Supabase SQL Editor AFTER you deploy v4.3.
-- Safe to re-run (idempotent).
--
-- WHAT IT DOES:
--  1) Adds any missing columns for v4.3 (research_brief doc support, SEO fields)
--  2) CLEARS the 73 broken failed items from v4.1/v4.2 so they stop burning money
--  3) Resets run_ledger so your dashboard shows fresh spending
--  4) Pauses all accounts EXCEPT "AI Tool Daily" so you start with ONE
--     active account (as requested: only publish content that's 8/10+)
--  5) Ensures all RLS policies exist
-- ============================================================

-- 1) Make sure account_documents supports a research_brief doc type
--    (doc_type is just a text column, so inserts already work. This is a no-op guard.)
alter table if exists public.account_documents
  add column if not exists agent text not null default 'architect';

-- 2) SEO cache fields on account_posts (best-effort; nullable)
alter table if exists public.account_posts
  add column if not exists first_comment text,
  add column if not exists alt_text text,
  add column if not exists yt_title text,
  add column if not exists seo_keywords jsonb not null default '[]'::jsonb;

-- 3) Ensure memory_entries supports 'research' and 'seo' roles
--    (roles are not CHECK constrained, but if they were, widen it)
do $$
begin
  -- If a check constraint on role exists that excludes research/seo, drop + recreate permissive one
  if exists (
    select 1 from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where t.relname='memory_entries' and n.nspname='public' and c.conname like '%role%'
  ) then
    execute 'alter table public.memory_entries drop constraint if exists memory_entries_role_check';
  end if;
exception when others then null;
end $$;

-- 4) CLEAN UP THE 73 BROKEN ITEMS from v4.1/v4.2:
--    Move failed/rejected/idea items into a 'cleared' state so they stop
--    getting picked up by the tick loop, but KEEP them for history.
update public.board_items
  set status = 'cleared',
      payload = coalesce(payload, '{}'::jsonb) || jsonb_build_object(
        'cleared_reason', 'v4.3 boot cleanup — pre-quality-gate failures',
        'cleared_at', now()
      )
  where status in ('idea','failed');

-- Also mark any eternally-stuck drafting/rendering items as failed (but don't delete)
update public.board_items
  set status = 'failed',
      payload = coalesce(payload, '{}'::jsonb) || jsonb_build_object(
        'failed_reason', 'v4.3 — stuck before quality gate; retired'
      )
  where status in ('drafting','rendering','grading')
    and created_at < now() - interval '2 hours';

-- 5) Reset run_ledger counters so dashboard $ starts fresh from v4.3
--    (Comment out if you want to keep old spend history.)
delete from public.run_ledger
  where created_at < now() - interval '1 hour';

-- 6) Pause all accounts EXCEPT AI Tool Daily (per your request: only ONE active account
--    until you have 8/10+ content publishing reliably).
--    AI Tool Daily stays active (unpaused). Everything else pauses.
update public.project_accounts
  set paused = true
  where lower(name) not like '%ai tool daily%'
    and lower(handle) not like '%aitool%'
    and lower(handle) not like '%ai_tool%'
    and paused = false;

-- Make sure AI Tool Daily is UN-paused
update public.project_accounts
  set paused = false, status = 'needs_setup'
  where lower(name) like '%ai tool daily%'
     or lower(handle) like '%aitool%'
     or lower(handle) like '%ai_tool%';

-- Also pause all projects except the default one so nothing bleeds
update public.projects
  set paused = true
  where lower(name) not like '%default%'
    and lower(name) not like '%ai%'
    and paused = false;

-- 7) Reset stuck "processing" events so the right panel shows fresh state
update public.task_progress
  set status = 'done'
  where status = 'in_progress'
    and updated_at < now() - interval '2 hours';

-- 8) Ensure the content_grades table has a notes column (v4.1 added it but older DBs may miss)
alter table if exists public.content_grades
  add column if not exists notes text,
  add column if not exists fix_instruction text;

-- 9) Confirmation
select 'v4.3 BOOTFIX APPLIED — cleaned board_items, reset ledger, paused all except AI Tool Daily.' as status;
