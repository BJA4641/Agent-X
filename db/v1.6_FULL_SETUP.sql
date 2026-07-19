-- ============================================================
-- Agent-X v1.6 + MCP — ONE-SHOT SETUP
-- Run this ONCE in Supabase → SQL Editor. Safe to re-run.
-- ============================================================

-- ============ A) TREND SCOUT TABLE ============
create table if not exists trend_items (
  id bigint generated always as identity primary key,
  tenant_id text not null default 'me',
  niche text not null default 'ai_tools',
  platform text not null default 'news',
  title text not null,
  url text not null,
  author text,
  views bigint not null default 0,
  engagement bigint not null default 0,
  heat int not null default 0,
  published_at timestamptz,
  scraped_at timestamptz not null default now()
);
create unique index if not exists trend_items_url on trend_items(url);
create index if not exists trend_items_hot on trend_items(niche, heat desc, scraped_at desc);
do $$ begin alter table trend_items enable row level security; exception when others then null; end $$;
drop policy if exists "read trends" on trend_items;
create policy "read trends" on trend_items for select to authenticated using (true);

-- ============ B) MULTI-PROJECT ============
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  name text not null,
  niche text,
  platforms jsonb not null default '[]'::jsonb,
  status text not null default 'active' check (status in ('active','paused')),
  cta text,
  created_at timestamptz not null default now()
);
create index if not exists projects_user_idx on public.projects(user_id, status);
alter table public.projects enable row level security;
drop policy if exists "own projects" on public.projects;
create policy "own projects" on public.projects for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- ============ C) AGENT MARKETPLACE + AFFILIATE ============
create table if not exists public.marketplace_agents (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  name text not null, tagline text, description text, category text,
  price_usd numeric(10,2) not null default 0,
  capabilities jsonb not null default '[]'::jsonb,
  demo_script jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default now()
);
alter table public.marketplace_agents enable row level security;
drop policy if exists "agents readable" on public.marketplace_agents;
create policy "agents readable" on public.marketplace_agents for select using (active = true);

create table if not exists public.affiliate_links (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id) on delete cascade,
  code text unique not null,
  created_at timestamptz not null default now()
);
alter table public.affiliate_links enable row level security;
drop policy if exists "own links" on public.affiliate_links;
create policy "own links" on public.affiliate_links for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

create table if not exists public.affiliate_clicks (
  id bigint generated always as identity primary key,
  code text not null, agent_slug text,
  created_at timestamptz not null default now()
);
create index if not exists aff_clicks_code_idx on public.affiliate_clicks(code, created_at desc);
alter table public.affiliate_clicks enable row level security;
drop policy if exists "referrer sees own clicks" on public.affiliate_clicks;
create policy "referrer sees own clicks" on public.affiliate_clicks for select
  using (exists (select 1 from public.affiliate_links l
                 where l.code = affiliate_clicks.code and l.user_id = auth.uid()));

create table if not exists public.agent_leads (
  id uuid primary key default gen_random_uuid(),
  agent_slug text not null, name text not null, email text not null, company text, message text,
  ref_code text,
  status text not null default 'new' check (status in ('new','contacted','closed_won','closed_lost')),
  sale_usd numeric(10,2), commission_usd numeric(10,2), commission_paid boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists agent_leads_ref_idx on public.agent_leads(ref_code, status);
alter table public.agent_leads enable row level security;
drop policy if exists "referrer sees own leads" on public.agent_leads;
create policy "referrer sees own leads" on public.agent_leads for select
  using (exists (select 1 from public.affiliate_links l
                 where l.code = agent_leads.ref_code and l.user_id = auth.uid()));

create or replace function public.fill_commission() returns trigger as $$
begin
  if new.status = 'closed_won' and new.sale_usd is not null then
    new.commission_usd := round(new.sale_usd * 0.50, 2);
  end if;
  return new;
end; $$ language plpgsql;
drop trigger if exists trg_fill_commission on public.agent_leads;
create trigger trg_fill_commission before insert or update on public.agent_leads
  for each row execute function public.fill_commission();

-- Seed the 6 demo agents ONLY if the marketplace is empty (idempotent)
insert into public.marketplace_agents (slug, name, tagline, description, category, price_usd, capabilities, demo_script)
select * from (values
  ('aria-support', 'Aria — Support Desk Agent', 'Answers customer questions from your own docs, 24/7.',
   'Aria is trained on the documents, FAQs and past tickets you upload during onboarding. She answers in your brand voice, escalates anything unsure to a human inbox, and never invents policies.',
   'Customer support', 290,
   '["Trained on your docs & FAQ","Brand-voice replies","Human escalation inbox","Multilingual","Weekly quality report"]'::jsonb,
   '[{"q":"What are your shipping times?","a":"Standard shipping is 3–5 business days inside the EU. That came from your store policy doc — want the express options too?"}]'::jsonb),
  ('scout-sdr', 'Scout — Outbound SDR Agent', 'Researches leads and drafts personalized outreach for your review.',
   'Scout builds prospect lists from criteria you set, researches each company from public pages, and drafts first-touch emails. Nothing is sent automatically — every draft lands in a review queue first.',
   'Sales', 390,
   '["Lead research from public sources","Personalized first-touch drafts","Review queue — you approve every send","CRM export (CSV)","Reply classification"]'::jsonb,
   '[{"q":"Find SaaS in Berlin hiring support","a":"I would search public job boards and company sites for Berlin SaaS teams with open support roles, then draft a one-line opener referencing each posting. Drafts go to your review queue — you send, not me."}]'::jsonb),
  ('quill-content', 'Quill — Content Writer Agent', 'Blog posts, product pages and newsletters in your voice.',
   'Quill studies writing samples you provide, then produces drafts with sources listed for every factual claim.',
   'Content', 190,
   '["Voice-matched drafts","Sources listed per claim","SEO outline mode","Rewrites & summaries","Markdown/Doc export"]'::jsonb,
   '[{"q":"Write an intro about our new pricing","a":"Give me the pricing page and one older post you like, and I will match its rhythm. Every number links back to the page you gave me — no invented stats."}]'::jsonb),
  ('atlas-research', 'Atlas — Research Analyst Agent', 'Digest of any market, competitor or topic with cited sources.',
   'Atlas reads the links and files you provide plus public sources, and returns structured briefs with findings, quotes, and a source list.',
   'Research', 240,
   '["Structured briefs with citations","Competitor snapshots","File & link ingestion","Fact vs inference separation","Weekly watchlist digests"]'::jsonb,
   '[{"q":"Summarize my 3 competitors pricing","a":"Send the three pricing URLs. I will return a table of plans, limits and positioning, each cell linked to the exact page section it came from."}]'::jsonb),
  ('clara-booking', 'Clara — Booking & Scheduling Agent', 'Turns inquiries into booked calls without back-and-forth.',
   'Clara connects to your calendar, offers real open slots, handles reschedules, and sends reminders — only inside the availability windows you define.',
   'Operations', 190,
   '["Calendar integration","Real availability only","Reschedule handling","Reminder messages","Timezone aware"]'::jsonb,
   '[{"q":"Book me with a client next week","a":"I see Tue 10:00, Wed 14:30 and Thu 09:00 open in your booking window. I will offer those three; when the client picks one, it lands on your calendar with a reminder."}]'::jsonb),
  ('ledger-ops', 'Ledger — Back-office Data Agent', 'Cleans, tags and files the data work nobody wants.',
   'Ledger takes recurring data chores — invoice tagging, CRM cleanup, spreadsheet merging — and runs them on schedule with a change log you can audit. Dry-run mode shows every change before it applies.',
   'Operations', 240,
   '["Scheduled data chores","Dry-run preview","Full change log","Spreadsheet & CSV native","Duplicate detection"]'::jsonb,
   '[{"q":"Clean my messy contact sheet","a":"Upload it and I will show a dry-run first: duplicates merged, emails fixed, rows flagged unreadable. Nothing changes until you approve the preview."}]'::jsonb)
) as v(s,n,t,d,c,p,cap,ds)
where not exists (select 1 from public.marketplace_agents where slug = v.s);

-- ============ D) MCP INTEGRATION (see section 4 of notes) ============
create table if not exists public.mcp_connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade not null,
  provider text not null,                    -- 'claude' | 'chatgpt' | 'gemini' | 'cursor' | 'custom'
  label text,
  access_token text not null,                -- one-shot token the external client uses
  scopes text[] not null default '{}',       -- e.g. {'content.queue','wallet.read','projects.read'}
  last_used_at timestamptz,
  created_at timestamptz not null default now(),
  revoked_at timestamptz
);
create unique index if not exists mcp_token_uidx on public.mcp_connections(access_token) where revoked_at is null;
create index if not exists mcp_user_idx on public.mcp_connections(user_id, created_at desc);
alter table public.mcp_connections enable row level security;
drop policy if exists "own mcp connections" on public.mcp_connections;
create policy "own mcp connections" on public.mcp_connections for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Verify counts
select 'setup complete' as status,
  (select count(*) from trend_items) as trend_items,
  (select count(*) from projects) as projects,
  (select count(*) from marketplace_agents) as marketplace_agents,
  (select count(*) from affiliate_links) as affiliate_links,
  (select count(*) from mcp_connections) as mcp_connections;
