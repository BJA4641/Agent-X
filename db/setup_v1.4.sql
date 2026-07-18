-- =====================================================================
-- Agent-X — COMPLETE SETUP SCRIPT (v1.4)
-- Run this ONE TIME in Supabase → SQL Editor. It is idempotent (safe to
-- re-run) and adds: wallets, agent_events, user_connections, brand_profiles,
-- profiles (niche+onboarding), and the helper views/functions the app needs.
-- It does NOT touch your existing board/ledger/settings/entitlements tables.
-- =====================================================================

-- Extension for encrypt/decrypt (safe; already exists on most Supabase projects)
create extension if not exists pgcrypto;

-- =====================================================================
-- 0. HELPER: decrypt/encrypt tokens using a server-held passphrase.
--    (We store the passphrase in app settings so you don't need GUC setup.)
-- =====================================================================
create or replace function _app_secret() returns text as $$
  select coalesce(
    (select value->>'secret' from settings where tenant_id='me' and key='app_secret'),
    'agentx-default-secret-change-me-in-settings'
  );
$$ language sql stable security definer;

create or replace function encrypt_token(plain text) returns text as $$
begin
  if plain is null or plain = '' then return null; end if;
  return encode(
    pgp_sym_encrypt_bytea(convert_to(plain,'UTF8'), _app_secret(), 'compress-algo=1,cipher-algo=aes256'),
    'base64'
  );
end;
$$ language plpgsql stable security definer;

create or replace function decrypt_token(cipher text) returns text as $$
begin
  if cipher is null then return null; end if;
  begin
    return convert_from(pgp_sym_decrypt_bytea(decode(cipher,'base64'), _app_secret()), 'UTF8');
  exception when others then return null; end;
end;
$$ language plpgsql stable security definer;

grant execute on function encrypt_token(text) to authenticated, service_role;
grant execute on function decrypt_token(text) to service_role;

-- =====================================================================
-- 1. USER PROFILES (niche picker + onboarding state)
-- =====================================================================
create table if not exists profiles (
  user_id       uuid primary key references auth.users(id) on delete cascade,
  display_name  text,
  niche         text,                    -- ai_tools, fitness, finance, cooking, etc.
  page_name     text,
  platforms     text[] default '{}',     -- ['instagram','youtube','tiktok']
  onboarding_step int not null default 0,-- 0=pick niche, 1=connect channels, 2=dashboard
  onboarded     boolean not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
alter table profiles enable row level security;
drop policy if exists "own profile" on profiles;
create policy "own profile" on profiles for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Auto-create a profile row when a user signs up
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (user_id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'name', split_part(new.email,'@',1)))
  on conflict (user_id) do nothing;
  return new;
end;
$$ language plpgsql security definer;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- =====================================================================
-- 2. USER CONNECTIONS (encrypted per-user OAuth/API tokens)
-- =====================================================================
create table if not exists user_connections (
  user_id       uuid not null references auth.users(id) on delete cascade,
  platform      text not null,           -- instagram|youtube|tiktok|x|linkedin|pinterest|facebook
  display_name  text,
  -- We store a REDACTED summary in credentials_json (e.g. account_id, username),
  -- secrets live encrypted in cred_enc (unavailable to the browser).
  credentials_json jsonb not null default '{}'::jsonb,
  cred_enc      text,                    -- encrypted JSON via encrypt_token()
  status        text not null default 'active'
                check (status in ('active','revoked','error')),
  last_test_at  timestamptz,
  error_message text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  primary key (user_id, platform)
);
create index if not exists connections_user_idx on user_connections(user_id);
alter table user_connections enable row level security;
drop policy if exists "own connections read" on user_connections;
drop policy if exists "own connections write" on user_connections;
create policy "own connections read" on user_connections for select
  using (auth.uid() = user_id);
create policy "own connections write" on user_connections for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- =====================================================================
-- 3. BRAND BIBLE (per-tenant voice/pillars/visuals)
-- =====================================================================
create table if not exists brand_profiles (
  user_id         uuid primary key references auth.users(id) on delete cascade,
  brand_name      text,
  vertical        text,
  voice_tone      jsonb not null default '{}'::jsonb,
  audience        jsonb not null default '[]'::jsonb,
  pillars         jsonb not null default '[]'::jsonb,
  visual_id       jsonb not null default '{}'::jsonb,
  do_list         jsonb not null default '[]'::jsonb,
  dont_list       jsonb not null default '[]'::jsonb,
  cta_line        text default 'Follow for more.',
  risk_register   jsonb not null default '[]'::jsonb,
  onboarding_done boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
alter table brand_profiles enable row level security;
drop policy if exists "own brand rw" on brand_profiles;
create policy "own brand rw" on brand_profiles for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- =====================================================================
-- 4. WALLET + USAGE BILLING
-- =====================================================================
create table if not exists wallets (
  user_id         uuid primary key references auth.users(id) on delete cascade,
  balance_usd     numeric(10,4) not null default 0,
  lifetime_spent  numeric(10,4) not null default 0,
  lifetime_topup  numeric(10,4) not null default 0,
  overdraft_limit numeric(10,4) not null default 0,
  paused          boolean not null default false,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
alter table wallets enable row level security;
drop policy if exists "own wallet" on wallets;
create policy "own wallet" on wallets for select
  using (auth.uid() = user_id);

create table if not exists wallet_transactions (
  id          bigint generated always as identity primary key,
  user_id     uuid not null references auth.users(id) on delete cascade,
  type        text not null check (type in ('deposit','consume','bonus','refund')),
  amount      numeric(10,4) not null,
  step        text,
  item_id     uuid references board_items(id) on delete set null,
  note        text,
  stripe_payment_id text,
  created_at  timestamptz not null default now()
);
create index if not exists wtx_user_ts on wallet_transactions(user_id, created_at desc);
alter table wallet_transactions enable row level security;
drop policy if exists "own wtx" on wallet_transactions;
create policy "own wtx" on wallet_transactions for select
  using (auth.uid() = user_id);

-- =====================================================================
-- 5. AGENT WORKSPACE (Slack-style live event stream)
-- =====================================================================
create table if not exists agent_events (
  id          bigint generated always as identity primary key,
  tenant_id   text not null default 'me',
  user_id     uuid references auth.users(id) on delete cascade,
  agent       text not null,
  action      text not null,
  item_id     uuid references board_items(id) on delete set null,
  message     text,
  status      text not null default 'info' check (status in ('info','success','warn','error','debate')),
  cost_usd    numeric(10,5) not null default 0,
  created_at  timestamptz not null default now()
);
create index if not exists ae_tenant_ts on agent_events(tenant_id, created_at desc);
create index if not exists ae_user_ts on agent_events(user_id, created_at desc);
alter table agent_events enable row level security;
-- Users see only their own events; service role (worker) sees all
drop policy if exists "own events" on agent_events;
create policy "own events" on agent_events for select
  using (auth.uid() = user_id);
-- Worker writes via service role; a convenience insert policy lets authenticated
-- users insert manual notes too (for comment/approval events):
drop policy if exists "insert events" on agent_events;
create policy "insert events" on agent_events for insert
  with check (auth.uid() = user_id or user_id is null);

-- =====================================================================
-- 6. NICHE LIBRARY (pre-populated niches for the picker)
-- =====================================================================
create table if not exists niches (
  slug        text primary key,
  name        text not null,
  emoji       text,
  starter_channels text[] default '{}',
  starter_queries  text[] default '{}',
  description text
);
alter table niches enable row level security;
drop policy if exists "niche read" on niches;
create policy "niche read" on niches for select using (true);

insert into niches (slug, name, emoji, starter_channels, starter_queries, description) values
  ('ai_tools','AI tools & tutorials','🤖',
    array['UCfyK3cTqplT9r_sr5R0y6Yw','UCJ6j84hGjh3C8E4UJdJ4Y_Q','UCHop-VRH1rFh4W8nLp8t9gw'],
    array['AI tools','ChatGPT tutorial','Claude AI','best AI apps'],
    'Short-form AI tutorials, tool walkthroughs, productivity hacks.'),
  ('fitness','Fitness & workouts','💪',
    array[]::text[], array['gym tips','home workout','fitness routine'],
    'Workout tips, form checks, nutrition, gym motivation.'),
  ('finance','Personal finance & investing','💰',
    array[]::text[], array['passive income','investing for beginners','side hustle'],
    'Money tips, investing explainers, side hustle blueprints.'),
  ('cooking','Cooking & recipes','🍳',
    array[]::text[], array['easy recipe','quick meal','cooking hack'],
    'Quick recipes, cooking hacks, meal prep.'),
  ('skincare','Skincare & beauty','🧴',
    array[]::text[], array['skincare routine','glow up','skin tips'],
    'Skincare science, routines, product reviews.'),
  ('gaming','Gaming','🎮',
    array[]::text[], array['gaming tips','new game','gameplay'],
    'Game clips, tips, easter eggs, tier lists.'),
  ('real_estate','Real estate','🏠',
    array[]::text[], array['real estate tips','first home','airbnb'],
    'Real estate investing, agent tips, home tours.'),
  ('saas','SaaS & B2B growth','📈',
    array[]::text[], array['saas growth','b2b marketing','startup tips'],
    'SaaS marketing, founder stories, growth hacks.'),
  ('coaching','Coaching & mindset','🧠',
    array[]::text[], array['self improvement','discipline','mindset'],
    'Motivation, mindset coaching, productivity.'),
  ('travel','Travel','✈️',
    array[]::text[], array['travel hack','cheap flights','hidden gem'],
    'Budget travel, itineraries, hidden gems.'),
  ('fashion','Fashion & style','👗',
    array[]::text[], array['outfit idea','style tip','fashion trend'],
    'Outfits, styling tips, trend reports.'),
  ('parenting','Parenting','👶',
    array[]::text[], array['parenting hack','baby tips','toddler'],
    'Parenting hacks, child development, relatable moments.'),
  ('crypto','Crypto & web3','₿',
    array[]::text[], array['crypto news','altcoin','bitcoin'],
    'Crypto news, alpha threads, risk-managed plays.'),
  ('music','Music production','🎵',
    array[]::text[], array['music production','beat making','fl studio'],
    'Producer tutorials, beat breakdowns, mixing tips.'),
  ('pets','Pets & animals','🐾',
    array[]::text[], array['cute dog','cat video','pet trick'],
    'Pet clips, training tips, wholesome content.'),
  ('diy','DIY & home improvement','🔨',
    array[]::text[], array['diy project','home hack','woodworking'],
    'DIY builds, tool tips, home makeovers.'),
  ('cars','Cars & auto','🚗',
    array[]::text[], array['car hack','first car','mods'],
    'Car reviews, mods, maintenance tips.'),
  ('education','Education & studying','📚',
    array[]::text[], array['study tip','exam hack','learn fast'],
    'Study techniques, exam prep, learning how to learn.'),
  ('productivity','Productivity','⚡',
    array[]::text[], array['productivity hack','notion template','time block'],
    'Productivity systems, Notion tours, life optimization.'),
  ('mental_health','Mental health','💚',
    array[]::text[], array['anxiety relief','therapy','self care'],
    'Mental wellness, coping strategies, self-care.')
on conflict (slug) do nothing;

-- =====================================================================
-- 7. Storage buckets (create via dashboard if these statements fail;
--    they require the s3 protocol and are easier to make by hand):
--    - media  (public, 500mb limit)
--    - proofs (private, 8mb limit)
--    - agent-avatars (public)
-- =====================================================================

-- Done.
select 'setup complete' as status;
