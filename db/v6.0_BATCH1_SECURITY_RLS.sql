-- =====================================================================
-- Agent-X v6.0 BATCH 1 — SECURITY: RLS LOCKDOWN
-- Enables Row Level Security (deny-all: RLS on, zero policies) on every
-- sensitive pipeline table. The worker (Railway) and web API routes use
-- the SERVICE ROLE key, which BYPASSES RLS — they keep working unchanged.
-- Only the public anon key gets locked out, which is the entire point.
--
-- ⚠ ONE POSSIBLE SIDE EFFECT: if any dashboard page reads one of these
-- tables directly from the BROWSER (lib/supabase/client.ts) instead of
-- through an API route, that page will show empty data after this runs.
-- That page was leaking sensitive data to the browser and must be moved
-- behind an API route — tell me which page broke and I'll patch it in
-- Batch 2. Do NOT roll this back to "fix" a page.
--
-- AFTER RUNNING: rotate the anon key in Supabase Dashboard ->
-- Settings -> API -> "Reset anon key", then update the env var on Vercel
-- (NEXT_PUBLIC_SUPABASE_ANON_KEY) and redeploy web.
-- =====================================================================

do $$
declare
  t text;
  tables text[] := array[
    'jobs','jobs_archive','agent_events','exec_decisions','settings',
    'roi_snapshots','capital_allocation','asset_library',
    'ceo_recommendations','revenue_events',
    'board_items','board_items_archive','trend_items','content_grades',
    'account_documents','performance','account_posts','experiments',
    'kpi_snapshots','memory','memory_entries','lessons','task_progress',
    'escalations','agent_leads','worker_health','mcp_connections',
    'marketplace_agents','projects','project_accounts','run_ledger',
    'affiliate_links','affiliate_clicks'
  ];
begin
  foreach t in array tables loop
    if exists (select 1 from pg_tables where schemaname='public' and tablename=t) then
      execute format('alter table public.%I enable row level security', t);
    end if;
  end loop;
end $$;

-- Verification: anything still exposed? (Should be only intentionally
-- public tables like waitlist, or tables with real user policies like profiles.)
select tablename as still_without_rls
from pg_tables p
join pg_class c on c.relname = p.tablename
join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public'
where p.schemaname = 'public' and c.relrowsecurity = false
order by 1;
