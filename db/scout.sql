-- ============================================================
-- TREND SCOUT — run ONCE in the Supabase SQL Editor.
-- Creates the trend_items table the Railway scout agent writes to
-- and the /trends desk reads from. Safe to re-run.
-- ============================================================

create table if not exists trend_items (
  id bigint generated always as identity primary key,
  tenant_id text not null default 'me',
  niche text not null default 'ai_tools',
  platform text not null default 'news',       -- reddit | news | hackernews | youtube
  title text not null,
  url text not null,
  author text,
  views bigint not null default 0,
  engagement bigint not null default 0,
  heat int not null default 0,                 -- 1-99: engagement x freshness
  published_at timestamptz,
  scraped_at timestamptz not null default now()
);

-- upsert key (scout writes with on_conflict=url)
create unique index if not exists trend_items_url on trend_items(url);
create index if not exists trend_items_hot on trend_items(niche, heat desc, scraped_at desc);

-- RLS: any logged-in user can READ trends; only the service key (Railway) writes.
do $$ begin alter table trend_items enable row level security; exception when others then null; end $$;

drop policy if exists "read trends" on trend_items;
create policy "read trends" on trend_items for select to authenticated using (true);

-- verify
select count(*) as trend_rows from trend_items;
