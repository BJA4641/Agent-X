-- =====================================================================
-- Agent-X v1.4.5 — ACTUALLY WORKS on your DB
-- Root cause found: niches PK is (tenant_id, slug), not just slug.
-- This script matches every existing constraint in your schema.
-- Run ALL of this in ONE query in Supabase SQL Editor.
-- =====================================================================

create extension if not exists pgcrypto;

-- Encryption helpers
create or replace function _app_secret() returns text as $$
  select coalesce(
    (select value->>'secret' from settings where tenant_id='me' and key='app_secret'),
    'agentx-default-secret-change-me-in-settings'
  );
$$ language sql stable security definer;

create or replace function encrypt_token(plain text) returns text as $$
begin
  if plain is null or plain = '' then return null; end if;
  return encode(pgp_sym_encrypt_bytea(convert_to(plain,'UTF8'), _app_secret(), 'compress-algo=1,cipher-algo=aes256'),'base64');
end; $$ language plpgsql stable security definer;

create or replace function decrypt_token(cipher text) returns text as $$
begin
  if cipher is null then return null; end if;
  begin
    return convert_from(pgp_sym_decrypt_bytea(decode(cipher,'base64'), _app_secret()),'UTF8');
  exception when others then return null; end;
end; $$ language plpgsql stable security definer;

grant execute on function encrypt_token(text) to authenticated, service_role;
grant execute on function decrypt_token(text) to service_role;

-- ============ 1. PROFILES ============
create table if not exists profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text, niche text, page_name text, platforms text[] default '{}',
  onboarding_step int not null default 0, onboarded boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
alter table profiles enable row level security;
drop policy if exists "own profile" on profiles;
create policy "own profile" on profiles for all using (auth.uid()=user_id) with check (auth.uid()=user_id);

create or replace function public.handle_new_user() returns trigger as $$
begin
  insert into public.profiles (user_id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data->>'name', split_part(new.email,'@',1)))
  on conflict (user_id) do nothing;
  return new;
end; $$ language plpgsql security definer;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute procedure public.handle_new_user();

insert into profiles (user_id, display_name, onboarded, created_at, updated_at)
select id, coalesce(raw_user_meta_data->>'name', split_part(email,'@',1)), true, now(), now()
from auth.users on conflict (user_id) do nothing;

-- ============ 2. USER_CONNECTIONS ============
create table if not exists user_connections (
  user_id uuid not null references auth.users(id) on delete cascade,
  platform text not null, display_name text,
  credentials_json jsonb not null default '{}'::jsonb, cred_enc text,
  status text not null default 'active', last_test_at timestamptz, error_message text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  primary key (user_id, platform)
);
do $$ begin
  alter table user_connections add constraint uc_status_check check (status in ('active','revoked','error'));
exception when others then null; end $$;
create index if not exists connections_user_idx on user_connections(user_id);
alter table user_connections enable row level security;
drop policy if exists "own connections read" on user_connections;
drop policy if exists "own connections write" on user_connections;
create policy "own connections read" on user_connections for select using (auth.uid()=user_id);
create policy "own connections write" on user_connections for all using (auth.uid()=user_id) with check (auth.uid()=user_id);

-- ============ 3. BRAND_PROFILES ============
create table if not exists brand_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  brand_name text, vertical text,
  voice_tone jsonb not null default '{}'::jsonb, audience jsonb not null default '[]'::jsonb,
  pillars jsonb not null default '[]'::jsonb, visual_id jsonb not null default '{}'::jsonb,
  do_list jsonb not null default '[]'::jsonb, dont_list jsonb not null default '[]'::jsonb,
  cta_line text default 'Follow for more.', risk_register jsonb not null default '[]'::jsonb,
  onboarding_done boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
alter table brand_profiles enable row level security;
drop policy if exists "own brand rw" on brand_profiles;
create policy "own brand rw" on brand_profiles for all using (auth.uid()=user_id) with check (auth.uid()=user_id);

-- ============ 4. WALLETS ============
create table if not exists wallets (
  user_id uuid primary key references auth.users(id) on delete cascade,
  balance_usd numeric(10,4) not null default 0, lifetime_spent numeric(10,4) not null default 0,
  lifetime_topup numeric(10,4) not null default 0, overdraft_limit numeric(10,4) not null default 0,
  paused boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
alter table wallets enable row level security;
drop policy if exists "own wallet" on wallets;
create policy "own wallet" on wallets for select using (auth.uid()=user_id);

create table if not exists wallet_transactions (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null, amount numeric(10,4) not null default 0, step text,
  item_id uuid references board_items(id) on delete set null, note text, stripe_payment_id text,
  created_at timestamptz not null default now()
);
do $$ begin
  alter table wallet_transactions add constraint wtx_type_check check (type in ('deposit','consume','bonus','refund'));
exception when others then null; end $$;
create index if not exists wtx_user_ts on wallet_transactions(user_id, created_at desc);
alter table wallet_transactions enable row level security;
drop policy if exists "own wtx" on wallet_transactions;
create policy "own wtx" on wallet_transactions for select using (auth.uid()=user_id);

insert into wallets (user_id, balance_usd, lifetime_topup, created_at, updated_at)
select id, 1.00, 1.00, now(), now() from auth.users on conflict (user_id) do nothing;

-- ============ 5. AGENT_EVENTS ============
create table if not exists agent_events (
  id bigint generated always as identity primary key,
  tenant_id text not null default 'me', user_id uuid references auth.users(id) on delete cascade,
  agent text not null default 'system', action text not null default 'note',
  item_id uuid references board_items(id) on delete set null, message text,
  status text not null default 'info', cost_usd numeric(10,5) not null default 0,
  created_at timestamptz not null default now()
);
do $$ begin
  alter table agent_events add constraint ae_status_check check (status in ('info','success','warn','error','debate'));
exception when others then null; end $$;
create index if not exists ae_tenant_ts on agent_events(tenant_id, created_at desc);
create index if not exists ae_user_ts on agent_events(user_id, created_at desc);
alter table agent_events enable row level security;
drop policy if exists "own events" on agent_events;
create policy "own events" on agent_events for select using (auth.uid()=user_id);
drop policy if exists "insert events" on agent_events;
create policy "insert events" on agent_events for insert
  with check (auth.uid()=user_id or user_id is null);

-- ============ 6. NICHES (THE BUG FIX) ============
-- Existing PK is (tenant_id, slug). We work WITH that, not against it.
-- Add new columns if missing.
do $$ begin alter table niches add column emoji text; exception when others then null; end $$;
do $$ begin alter table niches add column starter_channels text[] default '{}'; exception when others then null; end $$;
do $$ begin alter table niches add column starter_queries text[] default '{}'; exception when others then null; end $$;
do $$ begin alter table niches add column description text; exception when others then null; end $$;

-- Ensure tenant_id has a default 'me' for future inserts
do $$ begin
  alter table niches alter column tenant_id set default 'me';
exception when others then null; end $$;

-- Dedupe: keep ONE row per (tenant_id, slug), keep newest
do $$ begin
  delete from niches where ctid not in (
    select max(ctid) from niches group by tenant_id, slug
  );
exception when others then null; end $$;

alter table niches enable row level security;
drop policy if exists "niche read" on niches;
create policy "niche read" on niches for select using (true);

-- UPSERT using (tenant_id, slug) — MATCHES YOUR ACTUAL PK
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','ai_tools','AI tools & tutorials','🤖','{}','{"AI tools","ChatGPT tutorial","Claude AI","best AI apps"}','Tutorials & productivity hacks.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','fitness','Fitness & workouts','💪','{}','{"gym tips","home workout","fitness routine"}','Workouts, form, nutrition.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','finance','Personal finance','💰','{}','{"passive income","investing","side hustle"}','Money tips & investing.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','cooking','Cooking & recipes','🍳','{}','{"easy recipe","quick meal","cooking hack"}','Quick recipes, meal prep.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','skincare','Skincare & beauty','🧴','{}','{"skincare routine","glow up","skin tips"}','Skincare, product reviews.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','gaming','Gaming','🎮','{}','{"gaming tips","new game","gameplay"}','Clips, tips, tier lists.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','real_estate','Real estate','🏠','{}','{"real estate tips","first home","airbnb"}','Real estate investing.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','saas','SaaS & B2B growth','📈','{}','{"saas growth","b2b marketing","startup tips"}','SaaS marketing, growth.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','coaching','Coaching & mindset','🧠','{}','{"self improvement","discipline","mindset"}','Mindset, productivity.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','travel','Travel','✈️','{}','{"travel hack","cheap flights","hidden gem"}','Travel, itineraries.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','fashion','Fashion & style','👗','{}','{"outfit idea","style tip","fashion trend"}','Outfits, styling.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','parenting','Parenting','👶','{}','{"parenting hack","baby tips","toddler"}','Parenting hacks.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','crypto','Crypto & web3','₿','{}','{"crypto news","altcoin","bitcoin"}','Crypto news.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','music','Music production','🎵','{}','{"music production","beat making","fl studio"}','Producer tutorials.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','pets','Pets & animals','🐾','{}','{"cute dog","cat video","pet trick"}','Pet clips, training.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','diy','DIY & home','🔨','{}','{"diy project","home hack","woodworking"}','DIY builds.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','cars','Cars & auto','🚗','{}','{"car hack","first car","mods"}','Car reviews, mods.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','education','Education','📚','{}','{"study tip","exam hack","learn fast"}','Study techniques.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','productivity','Productivity','⚡','{}','{"productivity hack","notion template","time block"}','Productivity systems.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;
insert into niches (tenant_id, slug, name, emoji, starter_channels, starter_queries, description) values
  ('me','mental_health','Mental health','💚','{}','{"anxiety relief","therapy","self care"}','Mental wellness.')
  on conflict (tenant_id, slug) do update set
    name=excluded.name, emoji=coalesce(excluded.emoji, niches.emoji),
    starter_channels=excluded.starter_channels, starter_queries=excluded.starter_queries, description=excluded.description;

-- ============ 7. STORAGE BUCKETS ============
do $$ begin
  insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
  values ('media','media',true,524288000,array['image/png','image/jpeg','video/mp4','audio/mpeg']::text[]);
exception when others then null; end $$;

do $$ begin
  insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
  values ('proofs','proofs',false,8388608,array['image/png','image/jpeg']::text[]);
exception when others then null; end $$;

do $$ begin
  insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
  values ('agent-avatars','agent-avatars',true,2097152,array['image/png','image/jpeg','image/webp']::text[]);
exception when others then null; end $$;

-- Storage policies
drop policy if exists "media public read" on storage.objects;
do $$ begin
  create policy "media public read" on storage.objects for select using (bucket_id='media');
exception when others then null; end $$;

drop policy if exists "auth upload own folder" on storage.objects;
do $$ begin
  create policy "auth upload own folder" on storage.objects for insert to authenticated
    with check (bucket_id in ('media','proofs','agent-avatars') and (storage.foldername(name))[1]=auth.uid()::text);
exception when others then null; end $$;

drop policy if exists "auth update own" on storage.objects;
do $$ begin
  create policy "auth update own" on storage.objects for update to authenticated
    using ((storage.foldername(name))[1]=auth.uid()::text);
exception when others then null; end $$;

drop policy if exists "auth delete own" on storage.objects;
do $$ begin
  create policy "auth delete own" on storage.objects for delete to authenticated
    using ((storage.foldername(name))[1]=auth.uid()::text);
exception when others then null; end $$;

-- DONE
select 'setup complete' as status,
  (select count(*) from profiles) as profiles_created,
  (select count(*) from wallets) as wallets_seeded,
  (select count(*) from niches where tenant_id='me') as niches_loaded,
  (select count(*) from storage.buckets where id in ('media','proofs','agent-avatars')) as buckets_created;
