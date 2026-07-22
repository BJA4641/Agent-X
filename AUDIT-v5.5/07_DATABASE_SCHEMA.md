# Database Schema (v5.5)

All tables live in `public` schema. RLS is **disabled** on all pipeline tables (service-role-only, single-tenant MVP). Legacy tables from v1-v4 coexist with v5 worker tables.

## Core worker tables (v5.0+)

| Table | Purpose | Created by | Key columns | Related workflows | Indexes | Status |
|---|---|---|---|---|---|---|
| `jobs` | Event-driven job queue | v5.0 | id (text PK), job_type, status ('queued','claimed','in_progress','wait_human','done','failed','blocked'), priority, payload, attempts, scheduled_for, account_id, cost_cents, idempotency_key | all workflows | jobs_status_priority, jobs_scheduled, jobs_type_status, jobs_worker, jobs_idempotency, jobs_account | ✅ active |
| `agent_events` | Event log (agent feeds) | v5.0 | id, emitter, type, status, action, message, subject (jsonb), cost_cents, account_id, item_id, ts (float epoch), created_at | all workflows (Agent Activity feed) | agent_events_tenant_ts, agent_events_item, agent_events_emitter, agent_events_job | ✅ active |
| `worker_health` | Worker heartbeat | v5.0 | worker_id PK, last_heartbeat_at, jobs_completed/failed/in_progress, version | ops.heartbeat | PK only | ✅ active |
| `exec_decisions` | v5.5 CEO spend audit trail | v5.5 | id bigint PK, account_id, job_id, department, action, estimated_cost_usd, expected_value_usd, expected_roi, success_probability, decision ('approve'/'deny'/'delay'/'reuse'/'cheaper'), reason, cheaper_alternative, reuse_asset_id, model_selected, ts | ceo.decide, content_pipeline | exec_depts, exec_dec_account | ✅ active, newly added v5.5 |
| `capital_allocation` | Per-account daily budget allocation | v5.5 | (tenant_id, account_id, day) PK, budget_usd, max_posts, focus ('grow'/'pause'/'profit'/'balanced'/'evergreen'/'engage'/'maintain'), note, model_tier, approved_by | ceo.daily_tick | PK only | ✅ active v5.5 |
| `roi_snapshots` | Per-account daily ROI rollup | v5.5 | id bigint PK, (tenant_id, account_id, day) unique, spend_usd, posts_published/planned, scripts_written, images_generated, videos_generated, api_calls, views/likes/comments/shares/saves/followers_gained, revenue_usd, affiliate_clicks/conversions, sponsorship/product revenue, roi_multiple, cost_per_follower/view/engagement | analytics, ceo.daily_tick | roi_day, roi_account_day | ⚠️ partial: revenue_usd hardcoded 0 until monetization |
| `asset_library` | Reusable scripts/hooks/images/voice/ideas by hash | v5.5 | id (content hash PK), account_id, niche, asset_type (script/hook/visual_prompt/image_path/video_path/voice_path/idea/caption/hashtag_set/seo), content, blob_path, metadata (jsonb), tags (text[]), usage_count, last_used_at, performance_score, cost_to_make_usd | ceo.reuse_search (finds), ceo.record_outcome (stores) | asset_type_niche (gin on tags) | ⚠️ partial: _store_asset never called; table empty |
| `ceo_recommendations` | Daily human-CEO action items | v5.5 | id bigint PK, severity ('info'/'action'/'critical'/'opportunity'), category, account_id, recommendation, reasoning, projected_roi, projected_value_usd, action_url, applied/dismissed booleans | ceo.daily_tick writes; ceo-v2 UI displays; CEO can Apply/Dismiss | ceo_rec_day, ceo_rec_open | ✅ active v5.5 |
| `kpi_snapshots` | Hourly KPI time-series | v5.1 | id bigint PK, metric (text), value (numeric), dimensions (jsonb), ts timestamptz | ops.snapshot | kpi_metric_ts | ✅ active |
| `trend_items` | Scouted trends | v5.0 | id uuid PK, title, url, platform, niche, heat (float), angle, metadata (jsonb), scraped_at (created_at in v5.5) | research.scout_run, editorial._pick_topics | trends_niche_heat | ✅ active |
| `account_documents` | 13 brand docs per account | v5.1 | (account_id, doc_type) PK, content, updated_at | brand_studio, brain._load_brand_context, /b/[aid] page | PK only | ✅ active |
| `memory` | Long-term account-scoped memory (v5) | v5.0 | id uuid PK, account_id, role, content, metadata (jsonb) | brain.write_script, knowledge.summarize_day | memory_account | ✅ active |
| `lessons` | Learned patterns from failures | v5.0 | id uuid PK, scope, subject_id, topic, lesson, evidence (jsonb), confidence, applied_at | analytics.post_mortem, grader rewrites | lessons_scope | ⚠️ written but not read by learning loop |
| `experiments` | Hook/content A/B tests | v5.1 | id uuid PK, account_id, item_id reference, topic, variants (jsonb), winner, winning_reason, status | experiments.create_hook_test/decide | experiments_account | ⚠️ stub; no winner selection yet |
| `escalations` | Human-desk items | v5.0 | id uuid PK, severity, summary, options, context, resolution, resolved_by (FK to auth.users), deadline_hours | human_desk.sync, grade failures | escalations_open | ✅ active |

## Legacy v1-v4 tables (still in use)

| Table | Purpose | Status |
|---|---|---|
| `board_items` | Content items through the pipeline: idea→drafted→approved→rejected→scheduled→published→failed→cleared→awaiting_approval→archived→queued→drafting→rendering→grading→paused | ✅ heavily used |
| `run_ledger` | Cost ledger (per-step spend). v5.4 added provider_label, cost_cents, department, action columns; v5.5 reuses it | ✅ actively written by ledger.py |
| `project_accounts` | User accounts with niche, handle, platforms, paused, daily_budget_usd, posts_per_day, brand_bible (jsonb), affiliate_urls (jsonb), sponsor | ✅ core |
| `projects` | Parent projects, user_id FK to auth.users | ✅ core |
| `settings` | KV tenant settings (kill_switch, daily_budget, autothrottle, model, model_t2i/ie/t2v/i2v/tts/vedit, schema_version, ceo_config, scout_last_ts) | ✅ core |
| `profiles` | User profiles, niche field for onboarding | ✅ active |
| `waitlist` | Landing page emails | ✅ active |
| `performance` | Post-level metrics (views/likes/comments/shares/saves/follows) | ⚠️ written by publish receipts; real API metrics pull not implemented |
| `content_grades` | Grade records per post | ✅ used by CQO |
| `wallets`, `wallet_transactions` | Demo wallet topups (v1) — NOT real spend (v5.3 wallet API now returns pipeline_spent for admins) | ⚠️ demo/legacy |
| `task_progress` | v1 progress table | ⚠️ legacy, not used by v5 workers |
| `entitlements` | User feature access (SaaS stub) | ⚠️ stub |
| `user_connections` | Social OAuth connections | ⚠️ partial |
| `mcp_connections` | MCP integrations (stub) | ⚠️ stub |
| `brand_profiles` | v1 brand profiles (legacy) | ⚠️ legacy, replaced by account_documents |
| `memory_entries` | v1 memory (legacy) | ⚠️ legacy, replaced by v5 memory |
| `account_posts` | Account posts list | ⚠️ partial |
| `affiliate_links`, `affiliate_clicks` | Affiliate tracking | ⚠️ clicks table unused; links stored in project_accounts.affiliate_urls |
| `marketplace_agents`, `agent_leads` | Marketplace (stub) | ❌ unused |

## Views

| View | Purpose | Status |
|---|---|---|
| `v_account_brief` | Convenience view joining project_accounts with executive_summary/brand_identity/tone_guide/visual_identity/content_rules + doc count, for /b/[aid] page | ✅ active |

## Functions & Triggers
**NONE.** No stored procedures, triggers, or PL/pgSQL functions. All logic is in Python/TypeScript (intentional — Supabase SQL editor had issues with DO blocks in v5.0/v5.2).

## Foreign Keys
- `agent_events.item_id → board_items(id) ON DELETE SET NULL`
- `agent_events.user_id → auth.users(id) ON DELETE SET NULL`
- `experiments.item_id → board_items(id) ON DELETE SET NULL`
- `escalations.item_id → board_items(id) ON DELETE SET NULL`
- `escalations.resolved_by → auth.users(id) ON DELETE SET NULL`
- Most v5 tables use loose UUID references without FKs intentionally (to avoid cross-table locking during queue operations).

## Indexes summary
- All foreign keys / common WHERE columns have plain btree indexes
- No partial indexes using STABLE functions (v5.2 IMMUTABLE bug taught us that)
- `trigram`/`gin` on asset_library.tags for tag search
- v5.5 added: `exec_depts`, `exec_dec_account`, `ledger_provider`, `ledger_tenant_day_dept`

## RLS status
- All pipeline/workers tables: **RLS DISABLED** (service role only)
- Tables exposed to users via Supabase client (projects, project_accounts, waitlist, profiles): RLS policies exist in earlier migrations but not enforced for service role
- **Recommendation:** Do not enable RLS on pipeline tables until Phase 4 multi-tenant SaaS.

## Known schema gaps
1. `trend_items.scraped_at` is NOT in the create statement (only `created_at`); scout code may reference `scraped_at` — verify
2. `run_ledger.item_id` is text but `board_items.id` is uuid; implicit cast works but should be aligned
3. No `updated_at` trigger on any table (all timestamps set app-side)
4. No row count limits / partitioning; tables will grow unbounded without archival
