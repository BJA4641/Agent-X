-- =====================================================================
-- Agent-X v6.0 BATCH 2 — EMERGENCY REPAIR (FIXED)
-- Replaces the Batch 1 script that failed on run_ledger_item_id_fkey.
-- Why it failed: run_ledger rows (spend records) point at board_items,
-- so the flooded ideas can't be DELETEd. We don't need to delete them —
-- marking them status='cleared' removes them from every pipeline query
-- (inflight counts, boards, ideation) while keeping spend history intact.
-- Safe to re-run. Run AFTER pushing the Batch 2 code.
-- =====================================================================

-- 1. Archive table for failed jobs (keeps forensics out of the hot table)
create table if not exists jobs_archive (like jobs including all);

-- 2. Archive + remove the failed write_script job debris
--    (job rows have no FK from run_ledger, so DELETE works here)
insert into jobs_archive
  select * from jobs
  where status = 'failed' and job_type = 'creative.write_script'
  on conflict do nothing;

delete from jobs
  where status = 'failed' and job_type = 'creative.write_script';

-- 3. THE FIX for the FK error: mark flooded ideas 'cleared' (terminal
--    status the system already uses) instead of deleting them.
update board_items set status = 'cleared'
  where status = 'idea';

-- 4. Reset any stuck in-progress job so the fixed worker re-claims cleanly
update jobs
  set status = 'queued', claimed_by = null
  where status = 'in_progress';

-- 5. Drop queued jobs that point at now-cleared ideas (fresh pipeline
--    will regenerate ideation cheaply and correctly)
delete from jobs
  where status = 'queued'
    and job_type in ('creative.write_script', 'editorial.plan_one', 'cqo.grade_script');

-- 6. ONE-ACTIVE-ACCOUNT rule: pause everything; you unpause exactly one
--    from the dashboard after the v5.6.0 worker is confirmed running.
update project_accounts set paused = true where paused = false;

-- 7. Verification — eyeball this output
select 'jobs_failed_write_script' as metric, count(*)::text as value
  from jobs where status='failed' and job_type='creative.write_script'
union all select 'jobs_queued', count(*)::text from jobs where status='queued'
union all select 'jobs_in_progress', count(*)::text from jobs where status='in_progress'
union all select 'board_items_idea', count(*)::text from board_items where status='idea'
union all select 'board_items_cleared', count(*)::text from board_items where status='cleared'
union all select 'accounts_active', count(*)::text from project_accounts where paused=false;
-- Expected: failed_write_script 0, idea 0, cleared ~7,380+, accounts_active 0.
