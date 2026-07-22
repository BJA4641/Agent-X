-- ======================================================
-- v5.5 PRODUCTION MIGRATION — CEO / ROI ENGINE
-- Autonomous capital allocation, spend gates, asset reuse.
-- Idempotent — safe to re-run.
-- ======================================================

-- 1) exec_decisions: every time an agent WANTS to spend money, the CEO
--    engine writes a row: what it wanted to do, expected ROI, approve/deny,
--    reason. This creates a full audit trail of every spending decision.
create table if not exists public.exec_decisions (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me',
    ts timestamptz not null default now(),
    account_id uuid,
    job_id text,
    department text not null,           -- cfo | ceo | editorial | creative | postprod | distribution | research
    action text not null,               -- ideate | write_script | render_image | render_video | tts | scout | distribute | ...
    estimated_cost_usd numeric(10,5) not null default 0,
    expected_value_usd numeric(10,5),   -- projected value if this succeeds
    expected_roi numeric(8,2),          -- ROI multiple (EV/cost, e.g. 5.0 = 5x)
    success_probability numeric(5,4),   -- 0..1
    decision text not null default 'approve',  -- approve | deny | delay | cheaper | reuse
    reason text not null default '',
    cheaper_alternative text,
    reuse_asset_id text,
    model_selected text,
    created_at timestamptz not null default now()
);
alter table public.exec_decisions disable row level security;
create index if not exists exec_depts on public.exec_decisions (tenant_id, department, ts desc);
create index if not exists exec_dec_account on public.exec_decisions (account_id, ts desc);

-- 2) roi_snapshots: per-account daily ROI so the CEO can make data-driven
--    budget allocation decisions. One row per account per day.
create table if not exists public.roi_snapshots (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me',
    account_id uuid not null,
    day date not null default current_date,
    -- spend side
    spend_usd numeric(10,5) not null default 0,
    posts_published int not null default 0,
    posts_planned int not null default 0,
    scripts_written int not null default 0,
    images_generated int not null default 0,
    videos_generated int not null default 0,
    api_calls int not null default 0,
    -- outcome side
    views numeric(14,2) not null default 0,
    likes numeric(14,2) not null default 0,
    comments numeric(14,2) not null default 0,
    shares numeric(14,2) not null default 0,
    saves numeric(14,2) not null default 0,
    followers_gained numeric(14,2) not null default 0,
    -- revenue side
    revenue_usd numeric(10,5) not null default 0,
    affiliate_clicks int not null default 0,
    affiliate_conversions int not null default 0,
    sponsorship_revenue_usd numeric(10,5) not null default 0,
    product_revenue_usd numeric(10,5) not null default 0,
    -- computed
    roi_multiple numeric(8,2),           -- revenue/spend (1.0 = breakeven)
    cost_per_follower numeric(10,5),
    cost_per_view numeric(12,7),
    cost_per_engagement numeric(10,5),
    created_at timestamptz not null default now(),
    unique (tenant_id, account_id, day)
);
alter table public.roi_snapshots disable row level security;
create index if not exists roi_day on public.roi_snapshots (tenant_id, day desc);
create index if not exists roi_account_day on public.roi_snapshots (account_id, day desc);

-- 3) asset_library: reusable scripts/hooks/visuals/voiceovers/ideas so we
--    never recreate what already exists. Keyed by hash of content.
create table if not exists public.asset_library (
    id text primary key,               -- content hash
    tenant_id text not null default 'me',
    account_id uuid,                   -- null = cross-account reusable
    niche text,
    asset_type text not null,          -- script | hook | visual_prompt | image_path | video_path | voice_path | idea | caption | hashtag_set | seo
    content text not null,             -- text content or json
    blob_path text,                    -- path in storage for media assets
    metadata jsonb not null default '{}'::jsonb,
    tags text[] not null default '{}',
    usage_count int not null default 0,
    last_used_at timestamptz,
    performance_score numeric(6,3),    -- average grade / engagement when used
    cost_to_make_usd numeric(8,4) not null default 0,
    created_at timestamptz not null default now()
);
alter table public.asset_library disable row level security;
create index if not exists asset_type_niche on public.asset_library (asset_type, niche);
create index if not exists asset_account on public.asset_library (account_id, asset_type);
create index if not exists asset_tags on public.asset_library using gin (tags);

-- 4) capital_allocation: current budget per account. CEO writes these rows
--    each day based on ROI history; worker reads them to know how much to produce.
create table if not exists public.capital_allocation (
    tenant_id text not null default 'me',
    account_id uuid not null,
    day date not null default current_date,
    budget_usd numeric(10,5) not null default 0,
    max_posts int not null default 0,
    focus text not null default 'balanced', -- grow | profit | maintain | pause | evergreen | engage
    note text not null default '',
    model_tier text not null default 'mix', -- free_only | cheap | mix | premium
    approved_by text not null default 'ceo', -- ceo | human | default
    decided_at timestamptz not null default now(),
    primary key (tenant_id, account_id, day)
);
alter table public.capital_allocation disable row level security;

-- 5) ceo_recommendations: daily recommendations for the human CEO (you).
create table if not exists public.ceo_recommendations (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me',
    ts timestamptz not null default now(),
    day date not null default current_date,
    severity text not null default 'info', -- info | action | critical | opportunity
    category text not null,                -- budget | pause | scale | reuse | creative | affiliate | sponsorship | content
    account_id uuid,
    recommendation text not null,
    reasoning text not null,
    projected_roi numeric(8,2),
    projected_value_usd numeric(10,5),
    action_url text,                       -- deep link into dashboard
    applied boolean not null default false,
    dismissed boolean not null default false,
    created_at timestamptz not null default now()
);
alter table public.ceo_recommendations disable row level security;
create index if not exists ceo_rec_day on public.ceo_recommendations (tenant_id, day desc);
create index if not exists ceo_rec_open on public.ceo_recommendations (tenant_id, dismissed, applied, ts desc);

-- 5b) revenue_events (v5.5 P0): affiliate clicks, sponsorship payouts, product sales.
--     Written by monetization pixel + ceo.record_outcome; consumed by _snapshot_roi
--     so roi_snapshots.revenue_usd is no longer hardcoded to 0.
create table if not exists public.revenue_events (
    id bigint generated always as identity primary key,
    tenant_id text not null default 'me',
    account_id uuid,
    item_id text,                              -- board_item id (post that earned it)
    amount_usd numeric(10,5) not null default 0,
    source text not null,                      -- affiliate | sponsor | product | tip | other
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
alter table public.revenue_events disable row level security;
create index if not exists rev_evt_acct_day on public.revenue_events (account_id, created_at desc);
create index if not exists rev_evt_source on public.revenue_events (source, created_at desc);

-- 6) Run ledger columns needed for ROI calculation
alter table public.run_ledger add column if not exists department text;
alter table public.run_ledger add column if not exists action text;
alter table public.run_ledger add column if not exists account_id uuid;
alter table public.run_ledger add column if not exists provider_label text;
alter table public.run_ledger add column if not exists cost_cents int not null default 0;
create index if not exists ledger_tenant_day_dept on public.run_ledger (tenant_id, created_at desc, department);

-- 7) Enforce a hard HOSTILE cap: kill_switch auto-trips when daily spend
--    exceeds 2x budget. The CEO engine will catch it earlier, but this is
--    the emergency brake.
insert into public.settings (tenant_id, key, value) values
    ('me', 'ceo_config', jsonb_build_object(
        'min_roi_threshold', 1.5,        -- require 1.5x ROI to approve new spend
        'max_daily_spend_multiplier', 2.0, -- hard cap at 2x budget
        'free_tier_preferred', true,     -- prefer free models when quality is close
        'reuse_before_generate', true,   -- search asset library first
        'scale_winning_brands', true,    -- auto-scale high-ROI accounts
        'pause_losers_after_days', 3,    -- pause accounts that lose $ for N days
        'new_account_daily_budget', 0.25 -- $0.25 max for cold-start accounts
    ))
on conflict (tenant_id, key) do update set value = excluded.value;

-- Schema version
insert into public.settings (tenant_id, key, value) values
    ('me', 'schema_version', jsonb_build_object('v','5.5','applied_at_epoch',extract(epoch from now())))
on conflict (tenant_id, key) do update set value = excluded.value;
