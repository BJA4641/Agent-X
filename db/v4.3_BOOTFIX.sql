-- ============================================================
-- Agent-X v4.3 — BOOT FIX + CLEANUP (FIXED v3 — no errors)
-- Run ONCE in Supabase SQL Editor AFTER Railway + Vercel are green.
-- Safe to re-run (idempotent). Every statement is guarded.
--
-- Fixes vs v2:
--  - Removed the broken UPDATE on task_progress (that table has no 'status' column).
--  - Also widen project_accounts.status and account_documents.doc_type checks
--    so new statuses/docs (strategizing->ready, research_brief etc.) don't fail.
--  - Safer constraint dropping (only drops constraints that exist).
-- ============================================================

-- ---------- 1) Widen check constraints that would block new values ----------

-- board_items.status — allow 'cleared', 'awaiting_approval', 'archived', 'queued',
-- 'drafting', 'rendering', 'grading' (v4.3 pipeline uses these).
DO $$
DECLARE cname text;
BEGIN
  FOR cname IN
    SELECT conname FROM pg_constraint c
      JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
     WHERE t.relname='board_items' AND n.nspname='public' AND c.contype='c'
  LOOP
    EXECUTE format('ALTER TABLE public.board_items DROP CONSTRAINT IF EXISTS %I', cname);
  END LOOP;
END $$;

ALTER TABLE public.board_items
  DROP CONSTRAINT IF EXISTS board_items_status_check;
ALTER TABLE public.board_items
  ADD CONSTRAINT board_items_status_check
  CHECK (status IN ('idea','drafting','drafted','awaiting_approval','approved',
                    'rejected','scheduled','reported','published','failed',
                    'rendering','grading','queued','cleared','archived'));

-- project_accounts.status — originally allowed ('needs_setup','architecting','strategizing','ready','paused').
-- v4.3 doesn't add new statuses, but widen to be safe if we add 'error' later.
DO $$
DECLARE cname text;
BEGIN
  FOR cname IN
    SELECT conname FROM pg_constraint c
      JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
     WHERE t.relname='project_accounts' AND n.nspname='public' AND c.contype='c' AND c.conname LIKE '%status%'
  LOOP
    EXECUTE format('ALTER TABLE public.project_accounts DROP CONSTRAINT IF EXISTS %I', cname);
  END LOOP;
END $$;
ALTER TABLE public.project_accounts
  DROP CONSTRAINT IF EXISTS project_accounts_status_check;
ALTER TABLE public.project_accounts
  ADD CONSTRAINT project_accounts_status_check
  CHECK (status IN ('needs_setup','architecting','strategizing','ready','paused','error'));

-- account_documents.doc_type — originally only 5 aliases. Add the 13 real docs
-- + research_brief so architect's upserts don't fail.
DO $$
DECLARE cname text;
BEGIN
  FOR cname IN
    SELECT conname FROM pg_constraint c
      JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
     WHERE t.relname='account_documents' AND n.nspname='public' AND c.contype='c'
  LOOP
    EXECUTE format('ALTER TABLE public.account_documents DROP CONSTRAINT IF EXISTS %I', cname);
  END LOOP;
END $$;
ALTER TABLE public.account_documents
  DROP CONSTRAINT IF EXISTS account_documents_doc_type_check;
ALTER TABLE public.account_documents
  ADD CONSTRAINT account_documents_doc_type_check
  CHECK (doc_type IN (
    -- old aliases
    'business_plan','brand_guidelines','tone_guide','visual_rules','content_rules',
    -- 13 new architect docs
    'executive_summary','vision_mission','revenue_model','brand_identity','visual_identity',
    'marketing_strategy','instagram_playbook','tiktok_playbook','youtube_playbook',
    'content_calendar','hashtags_seo','production_sop',
    -- research bonus
    'research_brief'
  ));

-- ---------- 2) Add any missing v4.3 columns ----------
ALTER TABLE IF EXISTS public.account_documents
  ADD COLUMN IF NOT EXISTS agent text NOT NULL DEFAULT 'architect';

ALTER TABLE IF EXISTS public.account_posts
  ADD COLUMN IF NOT EXISTS first_comment text,
  ADD COLUMN IF NOT EXISTS alt_text text,
  ADD COLUMN IF NOT EXISTS yt_title text,
  ADD COLUMN IF NOT EXISTS seo_keywords jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE IF EXISTS public.projects
  ADD COLUMN IF NOT EXISTS paused boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS daily_budget_usd numeric(10,2) NOT NULL DEFAULT 2.00;

ALTER TABLE IF EXISTS public.project_accounts
  ADD COLUMN IF NOT EXISTS paused boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS daily_budget_usd numeric(10,2) NOT NULL DEFAULT 0.50,
  ADD COLUMN IF NOT EXISTS posts_per_day int NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS platforms_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS config jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS avatar_emoji text NOT NULL DEFAULT '🤖';

-- Drop any tight CHECK on memory_entries.role so research/seo/system can write
DO $$
DECLARE cname text;
BEGIN
  FOR cname IN
    SELECT conname FROM pg_constraint c
      JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
     WHERE t.relname='memory_entries' AND n.nspname='public' AND c.contype='c'
  LOOP
    EXECUTE format('ALTER TABLE public.memory_entries DROP CONSTRAINT IF EXISTS %I', cname);
  END LOOP;
EXCEPTION WHEN undefined_table THEN
  -- memory_entries doesn't exist yet — that's fine, v4.1 migration creates it
  NULL;
END $$;

ALTER TABLE IF EXISTS public.content_grades
  ADD COLUMN IF NOT EXISTS notes text,
  ADD COLUMN IF NOT EXISTS fix_instruction text;

-- ---------- 3) Ensure memory_entries + content_grades tables exist (idempotent) ----------
CREATE TABLE IF NOT EXISTS public.memory_entries (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id text NOT NULL DEFAULT 'me',
  project_id uuid REFERENCES public.projects(id) ON DELETE CASCADE,
  account_id uuid REFERENCES public.project_accounts(id) ON DELETE CASCADE,
  role text NOT NULL,
  content text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS memory_account_idx ON public.memory_entries(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS memory_project_idx ON public.memory_entries(project_id, created_at DESC);
ALTER TABLE public.memory_entries ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "own memory" ON public.memory_entries;
CREATE POLICY "own memory" ON public.memory_entries FOR ALL
  USING (
    (account_id IS NOT NULL AND EXISTS (SELECT 1 FROM public.project_accounts a WHERE a.id=account_id AND a.user_id=auth.uid()))
    OR
    (project_id IS NOT NULL AND EXISTS (SELECT 1 FROM public.projects p WHERE p.id=project_id AND p.user_id=auth.uid()))
  )
  WITH CHECK (
    (account_id IS NOT NULL AND EXISTS (SELECT 1 FROM public.project_accounts a WHERE a.id=account_id AND a.user_id=auth.uid()))
    OR
    (project_id IS NOT NULL AND EXISTS (SELECT 1 FROM public.projects p WHERE p.id=project_id AND p.user_id=auth.uid()))
  );

CREATE TABLE IF NOT EXISTS public.content_grades (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id text NOT NULL DEFAULT 'me',
  post_id uuid REFERENCES public.account_posts(id) ON DELETE CASCADE,
  item_id uuid REFERENCES public.board_items(id) ON DELETE CASCADE,
  grader text NOT NULL DEFAULT 'grader',
  hook int NOT NULL CHECK (hook BETWEEN 1 AND 10),
  visuals int NOT NULL CHECK (visuals BETWEEN 1 AND 10),
  pacing int NOT NULL CHECK (pacing BETWEEN 1 AND 10),
  audio int NOT NULL CHECK (audio BETWEEN 1 AND 10),
  caption int NOT NULL CHECK (caption BETWEEN 1 AND 10),
  cta int NOT NULL CHECK (cta BETWEEN 1 AND 10),
  overall numeric(3,1) NOT NULL,
  passed boolean NOT NULL DEFAULT false,
  notes text,
  fix_instruction text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS grades_post_idx ON public.content_grades(post_id, created_at DESC);
CREATE INDEX IF NOT EXISTS grades_item_idx ON public.content_grades(item_id, created_at DESC);
ALTER TABLE public.content_grades ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "own grades" ON public.content_grades;
CREATE POLICY "own grades" ON public.content_grades FOR SELECT
  USING (
    (post_id IS NOT NULL AND EXISTS (
      SELECT 1 FROM public.account_posts p JOIN public.project_accounts a ON a.id=p.account_id
      WHERE p.id=content_grades.post_id AND a.user_id=auth.uid()
    ))
    OR (item_id IS NOT NULL)
  );
DROP POLICY IF EXISTS "service inserts grades" ON public.content_grades;
CREATE POLICY "service inserts grades" ON public.content_grades FOR INSERT WITH CHECK (true);

-- ---------- 4) CLEANUP old failures ----------
-- Move 73 broken items to 'cleared' so they stop re-queueing
UPDATE public.board_items
  SET status = 'cleared',
      payload = COALESCE(payload, '{}'::jsonb) || jsonb_build_object(
        'cleared_reason', 'v4.3 boot cleanup — pre-quality-gate failures',
        'cleared_at', now()
      )
  WHERE status IN ('idea','failed');

-- Mark eternally-stuck items as failed
UPDATE public.board_items
  SET status = 'failed',
      payload = COALESCE(payload, '{}'::jsonb) || jsonb_build_object(
        'failed_reason', 'v4.3 — stuck before quality gate; retired'
      )
  WHERE status IN ('drafting','rendering','grading','queued')
    AND created_at < now() - interval '2 hours';

-- ---------- 5) Reset run_ledger so dashboard $ starts fresh ----------
-- (Safe — table always exists; if you don't want this, comment out these 2 lines.)
DELETE FROM public.run_ledger WHERE created_at < now() - interval '1 hour';

-- ---------- 6) PAUSE EVERYTHING EXCEPT AI TOOL DAILY ----------
UPDATE public.project_accounts
  SET paused = true
  WHERE paused = false
    AND lower(name) NOT LIKE '%ai tool daily%'
    AND lower(handle) NOT LIKE '%aitool%'
    AND lower(handle) NOT LIKE '%ai_tool%'
    AND lower(handle) NOT LIKE '%aitoolsdaily%';

-- Un-pause AI Tool Daily and reset it so architect writes the 13-doc plan fresh
UPDATE public.project_accounts
  SET paused = false,
      status = 'needs_setup'
  WHERE lower(name) LIKE '%ai tool daily%'
     OR lower(handle) LIKE '%aitool%'
     OR lower(handle) LIKE '%ai_tool%'
     OR lower(handle) LIKE '%aitoolsdaily%';

-- Pause any projects not related to AI/default
UPDATE public.projects
  SET paused = true
  WHERE paused = false
    AND lower(name) NOT LIKE '%default%'
    AND lower(name) NOT LIKE '%ai%';

-- ---------- 7) Done ----------
SELECT 'v4.3 BOOTFIX v3 APPLIED ✓ — constraints widened, old failures cleared ($ reset), only AI Tool Daily active.' AS status;
