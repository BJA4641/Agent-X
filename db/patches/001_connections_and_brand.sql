-- ============================================================
-- Agent-X patch 001: Per-user channel connections + Brand Bible
-- Run in Supabase SQL editor AFTER db/schema.sql
-- ============================================================

-- Encryption helper (pgsodium is available on paid Supabase; free tier falls
-- back to a server-side-secret XOR through a vaulted SECURITY DEFINER function).
-- For production, swap in pgsodium or a KMS. This block uses a simple
-- encrypt/decrypt wrapper so your web tier never stores plaintext tokens.

create extension if not exists pgcrypto;

-- Server-side secret stored as a GUC (set in Settings → Database → "postgres GUC").
-- Never expose this to the client or commit it. Example from SQL editor:
--   alter database postgres set app.encryption_key to 'REPLACE-ME-64-HEX-CHARS';
create or replace function _enc_key() returns bytea as $$
  select decode(current_setting('app.encryption_key', true), 'hex');
$$ language sql stable;

-- ---------- CHANNEL CONNECTIONS (OAuth / API keys per user) ----------
create table if not exists user_connections (
  user_id       uuid not null references auth.users(id) on delete cascade,
  platform      text not null,
  -- instagram | youtube | tiktok | x | linkedin | pinterest | facebook | threads
  credentials   jsonb not null default '{}'::jsonb,
  -- Encrypted envelope: never store plaintext. See _encrypt/_decrypt below.
  cred_enc      text,
  display_name  text,
  status        text not null default 'active' check (status in ('active','revoked','error')),
  last_test_at  timestamptz,
  error_message text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  primary key (user_id, platform)
);
create index if not exists connections_user on user_connections(user_id);
alter table user_connections enable row level security;

-- Users can read/update/delete only their own rows.
create policy "own connections read" on user_connections
  for select using (auth.uid() = user_id);
create policy "own connections insert" on user_connections
  for insert with check (auth.uid() = user_id);
create policy "own connections update" on user_connections
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "own connections delete" on user_connections
  for delete using (auth.uid() = user_id);

-- ---------- BRAND BIBLE (voice, audience, pillars, visual ID) ----------
create table if not exists brand_profiles (
  user_id         uuid primary key references auth.users(id) on delete cascade,
  brand_name      text,
  vertical        text,
  -- Core brand identity (filled by the brand agent from onboarding questionnaire)
  voice_tone      jsonb not null default '{}'::jsonb,
  -- { formality: "casual|conversational|authoritative", humor: "none|dry|bold",
  --   person: "1st|2nd|3rd", emoji_policy: "none|light|heavy",
  --   forbidden_words: [], sentence_length: "short|mixed|long",
  --   example_lines: [] }
  audience        jsonb not null default '[]'::jsonb,
  -- [{ name, age_range, gender?, pain_points:[], desires:[], media_diet:[] }]
  pillars         jsonb not null default '[]'::jsonb,
  -- ["Ingredient science", "Sustainability", ...]
  visual_id       jsonb not null default '{}'::jsonb,
  -- { palette: {primary:"#...", secondary:"#...", accent:"#..."},
  --   fonts: {heading, body}, imagery_style, logo_url, safe_zones }
  do_list         jsonb not null default '[]'::jsonb,
  dont_list       jsonb not null default '[]'::jsonb,
  cta_line        text default 'Follow for more.',
  risk_register   jsonb not null default '[]'::jsonb,
  publishing_prefs jsonb not null default '{}'::jsonb,
  -- { platforms:[{name, cadence_per_week, optimal_times:[], hashtags:[]}],
  --   promo_ratio:0.15, rapid_response_slots:2 }
  onboarding_done boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
alter table brand_profiles enable row level security;
create policy "own brand read" on brand_profiles for select using (auth.uid() = user_id);
create policy "own brand write" on brand_profiles for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ---------- PIPELINE: service role helpers ----------
-- When the pipeline needs to read a user's connection, it uses the SERVICE
-- ROLE key (bypasses RLS), so no policy is needed for worker reads. We add
-- convenience views.
create or replace view active_connections as
  select user_id, platform, credentials, display_name, last_test_at
  from user_connections where status = 'active';

create or replace view onboarded_brands as
  select user_id, brand_name, vertical, voice_tone, audience, pillars,
         visual_id, cta_line, publishing_prefs, do_list, dont_list, risk_register
  from brand_profiles where onboarding_done = true;
