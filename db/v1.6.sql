-- ============================================================
-- Agent-X v1.6 — multi-project + agent marketplace + affiliate
-- Run AFTER db/scout.sql. Safe to re-run (idempotent).
-- ============================================================

-- ---------- 1) PROJECTS: run several niches/brands at once ----------
create table if not exists public.projects (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references auth.users(id) on delete cascade,
  name        text not null,
  niche       text,
  platforms   jsonb not null default '[]'::jsonb,
  status      text not null default 'active' check (status in ('active','paused')),
  cta         text,
  created_at  timestamptz not null default now()
);
create index if not exists projects_user_idx on public.projects(user_id, status);
alter table public.projects enable row level security;
drop policy if exists "own projects" on public.projects;
create policy "own projects" on public.projects
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
-- (pipeline uses the service key, which bypasses RLS, to read all active projects)

-- ---------- 2) AGENT MARKETPLACE: our own original agents ----------
create table if not exists public.marketplace_agents (
  id           uuid primary key default gen_random_uuid(),
  slug         text unique not null,
  name         text not null,
  tagline      text,
  description  text,
  category     text,
  price_usd    numeric(10,2) not null default 0,
  capabilities jsonb not null default '[]'::jsonb,
  demo_script  jsonb not null default '[]'::jsonb,  -- scripted Q&A preview, clearly labeled in UI
  active       boolean not null default true,
  created_at   timestamptz not null default now()
);
alter table public.marketplace_agents enable row level security;
drop policy if exists "agents readable" on public.marketplace_agents;
create policy "agents readable" on public.marketplace_agents for select using (active = true);

-- ---------- 3) AFFILIATE: every user gets a referral code, 50% commission ----------
create table if not exists public.affiliate_links (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid unique references auth.users(id) on delete cascade,
  code       text unique not null,
  created_at timestamptz not null default now()
);
alter table public.affiliate_links enable row level security;
drop policy if exists "own links" on public.affiliate_links;
create policy "own links" on public.affiliate_links
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create table if not exists public.affiliate_clicks (
  id         bigint generated always as identity primary key,
  code       text not null,
  agent_slug text,
  created_at timestamptz not null default now()
);
create index if not exists aff_clicks_code_idx on public.affiliate_clicks(code, created_at);
alter table public.affiliate_clicks enable row level security;
drop policy if exists "referrer sees own clicks" on public.affiliate_clicks;
create policy "referrer sees own clicks" on public.affiliate_clicks for select
  using (exists (select 1 from public.affiliate_links l where l.code = affiliate_clicks.code and l.user_id = auth.uid()));

-- Leads from the PUBLIC /agents page. Sales are closed by you; when a lead is
-- marked closed_won with sale_usd, commission_usd = 50% is owed to ref_code owner.
create table if not exists public.agent_leads (
  id              uuid primary key default gen_random_uuid(),
  agent_slug      text not null,
  name            text not null,
  email           text not null,
  company         text,
  message         text,
  ref_code        text,
  status          text not null default 'new' check (status in ('new','contacted','closed_won','closed_lost')),
  sale_usd        numeric(10,2),
  commission_usd  numeric(10,2),
  commission_paid boolean not null default false,
  created_at      timestamptz not null default now()
);
create index if not exists agent_leads_ref_idx on public.agent_leads(ref_code, status);
alter table public.agent_leads enable row level security;
drop policy if exists "referrer sees own leads" on public.agent_leads;
create policy "referrer sees own leads" on public.agent_leads for select
  using (exists (select 1 from public.affiliate_links l where l.code = agent_leads.ref_code and l.user_id = auth.uid()));
-- inserts + admin updates happen server-side via the service role only.

-- auto-fill 50% commission whenever you close a sale
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

-- ---------- 4) SEED: six ORIGINAL Agent-X marketplace agents ----------
insert into public.marketplace_agents (slug, name, tagline, description, category, price_usd, capabilities, demo_script) values
('aria-support', 'Aria — Support Desk Agent', 'Answers customer questions from your own docs, 24/7.',
 'Aria is trained on the documents, FAQs and past tickets you upload during onboarding. She answers in your brand voice, escalates anything she is not sure about to a human inbox, and never invents policies.',
 'Customer support', 290,
 '["Trained on your docs & FAQ","Brand-voice replies","Human escalation inbox","Multilingual","Weekly answer-quality report"]',
 '[{"q":"What are your shipping times?","a":"Standard shipping is 3–5 business days inside the EU. I pulled that from the store policy doc you gave me — want the express options too?"},{"q":"I want a refund","a":"I can start that. Your policy allows refunds within 14 days of delivery. I''ll open the request and a teammate confirms the payout — nothing is finalized without a human OK."}]'),
('scout-sdr', 'Scout — Outbound SDR Agent', 'Researches leads and drafts personalized outreach for your review.',
 'Scout builds prospect lists from criteria you set, researches each company from public pages, and drafts first-touch emails. Nothing is sent automatically — every draft lands in a review queue first.',
 'Sales', 390,
 '["Lead research from public sources","Personalized first-touch drafts","Review queue — you approve every send","CRM export (CSV)","Reply classification"]',
 '[{"q":"Find SaaS companies in Berlin that hire support staff","a":"I''d search public job boards and company sites for Berlin SaaS teams with open support roles, then draft a one-line opener referencing each posting. Drafts go to your review queue — you send, not me."}]'),
('quill-content', 'Quill — Content Writer Agent', 'Blog posts, product pages and newsletters in your voice.',
 'Quill studies writing samples you provide, then produces drafts with sources listed for every factual claim. Built for teams that want volume without losing their voice.',
 'Content', 190,
 '["Voice-matched drafts","Sources listed per claim","SEO outline mode","Rewrites & summaries","Export to Markdown/Docs"]',
 '[{"q":"Write an intro about our new pricing","a":"Give me the pricing page and one older post you like, and I''ll match its rhythm. Every number in my draft links back to the page you gave me — no invented stats."}]'),
('atlas-research', 'Atlas — Research Analyst Agent', 'Digest of any market, competitor or topic with cited sources.',
 'Atlas reads the links and files you provide plus public sources, and returns structured briefs: findings, quotes, and a source list. Positions clearly marked as inference are separated from sourced facts.',
 'Research', 240,
 '["Structured briefs with citations","Competitor snapshots","File & link ingestion","Fact vs. inference separation","Weekly watchlist digests"]',
 '[{"q":"Summarize my 3 competitors'' pricing","a":"Send the three pricing URLs. I''ll return a table of plans, limits and positioning, each cell linked to the exact page section it came from."}]'),
('clara-booking', 'Clara — Booking & Scheduling Agent', 'Turns inquiries into booked calls without back-and-forth.',
 'Clara connects to your calendar, offers real open slots, handles reschedules, and sends reminders. She only books inside the availability windows you define.',
 'Operations', 190,
 '["Calendar integration","Real availability only","Reschedule handling","Reminder messages","Timezone aware"]',
 '[{"q":"Book me with a client next week","a":"I see Tue 10:00, Wed 14:30 and Thu 09:00 open in your booking window. I''ll offer those three; when the client picks one, it lands on your calendar with a reminder set."}]'),
('ledger-ops', 'Ledger — Back-office Data Agent', 'Cleans, tags and files the data work nobody wants.',
 'Ledger takes recurring data chores — invoice tagging, CRM cleanup, spreadsheet merging — and runs them on schedule with a change log you can audit. Dry-run mode shows every change before it applies.',
 'Operations', 240,
 '["Scheduled data chores","Dry-run preview","Full change log","Spreadsheet & CSV native","Duplicate detection"]',
 '[{"q":"Clean my messy contact sheet","a":"Upload it and I''ll show a dry-run first: 41 duplicates merged, 12 emails fixed, 7 rows flagged unreadable. Nothing changes until you approve the preview."}]')
on conflict (slug) do nothing;
