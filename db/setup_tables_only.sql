-- =====================================================================
-- Agent-X v1.4.6 — MINIMAL TABLE SETUP (run only if v1.4.5 didn't finish)
-- If you already saw 'setup complete' from a previous run, SKIP THIS FILE.
-- Only creates the 6 NEW tables the UI needs. Does NOT touch existing
-- board_items/run_ledger/performance/settings/niches/task_progress/etc.
-- =====================================================================
create extension if not exists pgcrypto;

-- Encryption helpers
create or replace function _app_secret() returns text as $$
  select coalesce((select value->>'secret' from settings where tenant_id='me' and key='app_secret'),'agentx-default-secret-change-me');
$$ language sql stable security definer;
create or replace function encrypt_token(plain text) returns text as $$
begin if plain is null or plain='' then return null; end if;
  return encode(pgp_sym_encrypt_bytea(convert_to(plain,'UTF8'),_app_secret(),'compress-algo=1,cipher-algo=aes256'),'base64');
end;$$ language plpgsql stable security definer;
create or replace function decrypt_token(cipher text) returns text as $$
begin if cipher is null then return null; end if;
  begin return convert_from(pgp_sym_decrypt_bytea(decode(cipher,'base64'),_app_secret()),'UTF8');
  exception when others then return null; end;
end;$$ language plpgsql stable security definer;
grant execute on function encrypt_token(text) to authenticated, service_role;
grant execute on function decrypt_token(text) to service_role;

-- PROFILES (create if not exists — never drops)
create table if not exists profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text, niche text, page_name text, platforms text[] default '{}',
  onboarding_step int not null default 0, onboarded boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
do $$ begin alter table profiles enable row level security; exception when others then null; end $$;
drop policy if exists "own profile" on profiles;
create policy "own profile" on profiles for all using(auth.uid()=user_id) with check(auth.uid()=user_id);
create or replace function public.handle_new_user() returns trigger as $$
begin insert into public.profiles(user_id,display_name) values(new.id,coalesce(new.raw_user_meta_data->>'name',split_part(new.email,'@',1))) on conflict(user_id) do nothing; return new;end;$$ language plpgsql security definer;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();
insert into profiles(user_id,display_name,onboarded,created_at,updated_at) select id,coalesce(raw_user_meta_data->>'name',split_part(email,'@',1)),true,now(),now() from auth.users on conflict(user_id) do nothing;

-- USER_CONNECTIONS
create table if not exists user_connections (
  user_id uuid not null references auth.users(id) on delete cascade, platform text not null,
  display_name text, credentials_json jsonb not null default '{}'::jsonb, cred_enc text,
  status text not null default 'active', last_test_at timestamptz, error_message text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  primary key(user_id,platform)
);
do $$ begin alter table user_connections add constraint uc_status_check check(status in('active','revoked','error'));exception when others then null;end$$;
create index if not exists connections_user_idx on user_connections(user_id);
do $$ begin alter table user_connections enable row level security; exception when others then null; end $$;
drop policy if exists "own connections read" on user_connections; drop policy if exists "own connections write" on user_connections;
create policy "own connections read" on user_connections for select using(auth.uid()=user_id);
create policy "own connections write" on user_connections for all using(auth.uid()=user_id) with check(auth.uid()=user_id);

-- BRAND_PROFILES
create table if not exists brand_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  brand_name text, vertical text, voice_tone jsonb not null default '{}'::jsonb,
  audience jsonb not null default '[]'::jsonb, pillars jsonb not null default '[]'::jsonb,
  visual_id jsonb not null default '{}'::jsonb, do_list jsonb not null default '[]'::jsonb,
  dont_list jsonb not null default '[]'::jsonb, cta_line text default 'Follow for more.',
  risk_register jsonb not null default '[]'::jsonb, onboarding_done boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
do $$ begin alter table brand_profiles enable row level security; exception when others then null; end $$;
drop policy if exists "own brand rw" on brand_profiles;
create policy "own brand rw" on brand_profiles for all using(auth.uid()=user_id) with check(auth.uid()=user_id);

-- WALLETS
create table if not exists wallets (
  user_id uuid primary key references auth.users(id) on delete cascade,
  balance_usd numeric(10,4) not null default 0, lifetime_spent numeric(10,4) not null default 0,
  lifetime_topup numeric(10,4) not null default 0, overdraft_limit numeric(10,4) not null default 0,
  paused boolean not null default false,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
do $$ begin alter table wallets enable row level security; exception when others then null; end $$;
drop policy if exists "own wallet" on wallets; create policy "own wallet" on wallets for select using(auth.uid()=user_id);

create table if not exists wallet_transactions (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null, amount numeric(10,4) not null default 0, step text,
  item_id uuid references board_items(id) on delete set null, note text, stripe_payment_id text,
  created_at timestamptz not null default now()
);
do $$ begin alter table wallet_transactions add constraint wtx_type_check check(type in('deposit','consume','bonus','refund'));exception when others then null;end$$;
create index if not exists wtx_user_ts on wallet_transactions(user_id,created_at desc);
do $$ begin alter table wallet_transactions enable row level security; exception when others then null; end $$;
drop policy if exists "own wtx" on wallet_transactions; create policy "own wtx" on wallet_transactions for select using(auth.uid()=user_id);
insert into wallets(user_id,balance_usd,lifetime_topup,created_at,updated_at) select id,1.00,1.00,now(),now() from auth.users on conflict(user_id) do nothing;

-- AGENT_EVENTS
create table if not exists agent_events (
  id bigint generated always as identity primary key, tenant_id text not null default 'me',
  user_id uuid references auth.users(id) on delete cascade,
  agent text not null default 'system', action text not null default 'note',
  item_id uuid references board_items(id) on delete set null, message text,
  status text not null default 'info', cost_usd numeric(10,5) not null default 0,
  created_at timestamptz not null default now()
);
do $$ begin alter table agent_events add constraint ae_status_check check(status in('info','success','warn','error','debate'));exception when others then null;end$$;
create index if not exists ae_tenant_ts on agent_events(tenant_id,created_at desc);
create index if not exists ae_user_ts on agent_events(user_id,created_at desc);
do $$ begin alter table agent_events enable row level security; exception when others then null; end $$;
drop policy if exists "own events" on agent_events; create policy "own events" on agent_events for select using(auth.uid()=user_id);
drop policy if exists "insert events" on agent_events; create policy "insert events" on agent_events for insert with check(auth.uid()=user_id or user_id is null);

-- STORAGE BUCKETS (silently skip if exist)
do $$ begin insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)values('media','media',true,524288000,array['image/png','image/jpeg','video/mp4','audio/mpeg']::text[]);exception when others then null;end$$;
do $$ begin insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)values('proofs','proofs',false,8388608,array['image/png','image/jpeg']::text[]);exception when others then null;end$$;
do $$ begin insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)values('agent-avatars','agent-avatars',true,2097152,array['image/png','image/jpeg','image/webp']::text[]);exception when others then null;end$$;
drop policy if exists "media public read" on storage.objects; do $$ begin create policy "media public read" on storage.objects for select using(bucket_id='media');exception when others then null;end$$;
drop policy if exists "auth upload own folder" on storage.objects; do $$ begin create policy "auth upload own folder" on storage.objects for insert to authenticated with check(bucket_id in('media','proofs','agent-avatars')and(storage.foldername(name))[1]=auth.uid()::text);exception when others then null;end$$;
drop policy if exists "auth update own" on storage.objects; do $$ begin create policy "auth update own" on storage.objects for update to authenticated using((storage.foldername(name))[1]=auth.uid()::text);exception when others then null;end$$;
drop policy if exists "auth delete own" on storage.objects; do $$ begin create policy "auth delete own" on storage.objects for delete to authenticated using((storage.foldername(name))[1]=auth.uid()::text);exception when others then null;end$$;

select 'setup complete' as status,
  (select count(*) from profiles) as profiles,
  (select count(*) from wallets) as wallets,
  (select count(*) from user_connections) as connections,
  (select count(*) from agent_events) as events;
