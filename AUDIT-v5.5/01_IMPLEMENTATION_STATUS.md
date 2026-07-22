# Agent-X Implementation Status Report (v5.5-CEO)
**Audit date:** 2026-07-20
**Audit type:** Mandatory engineering audit before next roadmap phase
**Auditor:** Self-audit (developer Claude Sonnet 4.5 on Arena.ai)
**Overall completion: 34%** (engine + foundation solid; production pipeline partial; revenue/monetization/autonomy skeleton only)

---

## Executive Summary

Agent-X has a solid, tested worker-engine foundation (v5.5) with an event-driven JobQueue, 32 registered job types across 16 departments, a SQLite-grade Postgres schema with 30+ tables, a Strangler-Fig wrapper around legacy v4 code, and a newly shipped v5.5 CEO/ROI gate. The web dashboard has basic Studio/console/business-plan pages.

However, the platform is **not end-to-end production-profitable yet**. Major gaps remain:
- **aisuite.py router exists but is not yet wired into legacy code paths** — the new 74-model catalog does NOT drive actual generation yet; visuals.py still calls Gemini directly; llm.py still uses its own Anthropic/Gemini/Groq/OpenRouter rotation. The UI selection at `/dashboard/models` is therefore **display-only** for now.
- **CEO gate is wired into only ONE job** (creative.write_script); other spend points (ideate, render, tts, video, scout, brand_studio) do NOT yet call ceo_decide().
- **Video generation (TTV/ITV) is NOT IMPLEMENTED** — aisuite.generate_video() has the Fal polling code but no creative.render_video worker job exists; postprod only stitches static frames via ffmpeg (no AI video yet).
- **No real revenue tracking** exists in roi_snapshots (revenue_usd hardcoded to 0). Affiliate clicks, sponsorships, and Stripe billing are scaffolded but not connected to real revenue data, so ROI math is speculative until monetization ships.
- **Publishing is dry-run by default** — Instagram uses Graph API if IG tokens exist; YouTube upload exists but has not been live-tested; TikTok publishing does not exist.
- **Asset library (asset_library) table exists but ceo._store_asset is not called anywhere yet** after successful posts — reuse can only find items already in the table.
- **Tests cover only 18/400+ code paths** (14 agentcore primitives + 4 worker-registration checks). No integration tests, no e2e tests, no CEO gate tests, no publisher tests.

The platform is best characterized as a **well-architected beta engine with one confirmed partially-working pipeline (script → image → ffmpeg-reel → dry-run publish)** plus a v5.5 ROI gate over that one path. It is not yet an autonomous media company; it is a working foundation with the right abstractions to become one.

---

## 1. Current platform version
- `settings.key = 'schema_version'` target: v5.5
- Worker banner: v5.5 (runner.py VERSION string)
- Web package.json: 1.4.1 (pre-v5, not bumped)
- Dockerfile CMD: `python cli.py worker`

## 2. Current roadmap phase
- Phase 1 (Blueprint): COMPLETE
- Phase 2 (Migration to worker engine): COMPLETE
- Phase 3 (Optimization + Autonomous Evolution): **IN PROGRESS — v5.5 CEO/ROI shipped, many sub-items incomplete**
- Phase 4 (v6 SaaS multi-tenant public launch): NOT STARTED

## 3. Overall completion: 34%
- Foundation/infra: 85%
- Content pipeline: 45%
- AI provider integration: 30% (catalog built; not wired)
- CEO/Capital allocation: 40% (gate on 1 job, dashboards, tables, logic done; wiring + real revenue missing)
- Publishing/distribution: 25% (dry-run works, IG/YT scaffolded, TikTok missing)
- Monetization/revenue: 15% (caption injection only)
- Analytics/learning: 20% (tables exist, KPI snapshots fire, learning loop not wired)
- SaaS multi-tenant/Revenue: 5% (Stripe checkout stub exists, no real billing)

---

## 4. Current Architecture
- **Web:** Next.js 14 App Router on Vercel, TypeScript, Supabase SSR, Tailwind-free inline CSS
- **API layer:** Next.js Route Handlers (serverless), service-role Supabase access
- **Worker:** Single Python 3 process on Railway, Dockerfile, entrypoint `cli.py worker`
- **Queue:** Postgres-backed job queue in `public.jobs` table, polled by Worker.run_forever(2.5s interval)
- **Event bus:** In-process EventBus publishing to `agent_events` table + memory (no cross-service bus yet)
- **DB:** Supabase Postgres, RLS disabled on pipeline tables (service-role-only)
- **Storage:** Supabase Storage (avatars, video outputs configured but not verified)
- **AI providers (catalog):** aisuite.py abstracts 74 models across 7 categories; currently only the legacy `agent/llm.py` and `agent/visuals.py` paths actually call providers

## 5. Organizational Chart (departments)

### Departments FULLY IMPLEMENTED (register handlers, boot-OK, run)
1. **finance (CFO)** — `pipeline/workers/departments/finance.py` (3 jobs: preflight, daily_report, killswitch_check)
2. **cqo (Chief Quality Officer)** — `pipeline/workers/departments/cqo.py` (1 job: grade_script)
3. **risk** — `pipeline/workers/departments/risk.py` (1 job: scan_content)
4. **portfolio** — `pipeline/workers/departments/portfolio.py` (2 jobs: boot, tick — orchestrator that drives account production)
5. **research** — `pipeline/workers/departments/research.py` (1 job: scout_run — calls legacy agent/scout.py)
6. **editorial** — `pipeline/workers/departments/editorial.py` (2 jobs: plan_one, ideate)
7. **creative** — `pipeline/workers/departments/creative.py` (2 jobs: write_script, render — render calls composer+visuals, has CEO gate)
8. **brand_studio** — `pipeline/workers/departments/brand_studio.py` (1 job: generate — generates 13 brand docs)
9. **ops** — `pipeline/workers/departments/ops.py` (2 jobs: heartbeat, snapshot)
10. **human_desk** — `pipeline/workers/departments/human_desk.py` (2 jobs: sync, rescan)
11. **experiments** — `pipeline/workers/departments/experiments.py` (2 jobs: create_hook_test, decide)
12. **knowledge** — `pipeline/workers/departments/knowledge.py` (1 job: summarize_day)
13. **analytics** — `pipeline/workers/departments/analytics.py` (2 jobs: collect_metrics, post_mortem)
14. **distribution** — `pipeline/workers/departments/distribution.py` (2 jobs: publish, cross_promote)
15. **monetization** — `pipeline/workers/departments/monetization.py` (2 jobs: inject, scan_inbox — **caption injection only; no real inbox scan**)
16. **ceo** (v5.5) — `pipeline/workers/departments/ceo.py` (5 jobs: decide, daily_tick, allocate_budgets, reuse_search, record_outcome)

### Departments PARTIALLY IMPLEMENTED
1. **postprod** — registered as `post.polish` but no dedicated video-edit job for AI upscale/captions premium; uses ffmpeg only
2. **monetization** — scan_inbox is a stub (no email scanner, no sponsor deal pipeline)
3. **analytics** — collect_metrics pulls from `performance` table but nothing writes performance except publish receipts; no real social-API metrics pull yet

### Departments MISSING (referenced in blueprint but no file)
- **sales** (sponsor outreach, deal desk)
- **legal** (FTC #ad compliance, content licensing)
- **community** (comment reply, DM)
- **pr** (trend jacking, viral seeding)
- **recruiting** (influencer partnerships)
- **infra/multi-service scaling** (split into scout/render/publish workers)

## 6. AI Agents Implemented
Every registered job_type is treated as an "agent." The worker is single-process; agents are functions registered via `w.register(job_type, handler)`.

See 04_AGENT_REGISTRY.json for the full machine-readable list. Key agents:

- **cfo.preflight** — auto-throttle, budget check (WORKING)
- **cqo.grade_script** — calls legacy grader.grade_post (WORKING)
- **portfolio.tick** — selects active account, enqueues ideate (WORKING)
- **research.scout_run** — calls scout.run() for trends (WORKING, zero LLM cost)
- **editorial.ideate** — picks topics, enqueues write_script (WORKING, niche-aware v5.3)
- **creative.write_script** — calls brain.write_script with CEO gate (WORKING, v5.5)
- **creative.render** — calls visuals+composer+tts to build MP4 via ffmpeg (PARTIAL — static frames only, no AI video)
- **brand_studio.generate** — calls architect to generate 13 brand docs (WORKING)
- **ops.heartbeat** — writes worker_health every 30s (WORKING)
- **ops.snapshot** — writes kpi_snapshots every 1h (WORKING)
- **distribution.publish** — calls publishing.publish, IG/YT (PARTIAL — dry runs without real keys)
- **ceo.daily_tick** — allocates budgets, writes recs (WORKING, but ROI math uses hardcoded $0 revenue)
- **ceo.decide** — inline and async CEO ROI gate (WIRED on creative.write_script ONLY)
- **monetization.inject** — adds "link in bio / #ad" lines (WORKING, trivial)
- **human_desk.sync** — surfaces escalations (WORKING, but approve/reject buttons untested end-to-end)

## 7. Current Workflows

### Workflow A: Bootstrap (on worker start)
1. runner.py enqueues portfolio.boot, ops.heartbeat, ops.snapshot, human_desk.sync, ceo.daily_tick
2. portfolio.boot → enqueues research.scout_run + portfolio.tick + cfo.daily_report + cfo.killswitch_check
3. When idle: heartbeat reschedules every 30s via idempotency key

### Workflow B: Content production (the only path that actually makes reels)
1. **portfolio.tick** → pick active account (single-account mode)
2. → enqueues **editorial.ideate** for that account
3. → **editorial.ideate** → _pick_topics() (niche-filtered from scout + evergreens + strategy) → calls board_add for each topic → enqueues **creative.write_script**
4. → **creative.write_script** → CEO gate (approve/deny/reuse/delay/cheaper) → brain.write_script (legacy, with niche hashtag fixes v5.4) → cqo.grade_script (rewrites up to MAX_REWRITES=2) → board_patch with script
5. → creative.render job (called from where? **NOT ENQUEUED automatically by write_script in current code** — write_script only enqueues cqo.grade_script. The render step is either driven by legacy orchestrator.tick() or manual. **GAP IDENTIFIED.**)
6. → **creative.render** (if triggered) → visuals.beat_frame() for each beat (Gemini image or procedural) → composer.render (ffmpeg concat) → voice (TTS, but only if ELEVENLABS key exists; otherwise silent) → enqueues distribution.publish
7. → **distribution.publish** → publishing.publish(item, caption) → IG/YT API or dry-run → enqueues analytics.collect_metrics (24h delay)
8. → **analytics.collect_metrics** (after delay) → pulls metrics → writes performance table

**Finding:** The handoff from `cqo.grade_script` (pass) to `creative.render` is NOT clearly wired in v5 workers. It appears the legacy `orchestrator.tick()` may have been driving the state machine. Need to verify and explicitly enqueue render after grade passes.

### Workflow C: Daily CEO review
1. ceo.daily_tick → _snapshot_roi → _allocate_budgets → _write_recommendations
2. CEO Console surfaces recommendations and audit trail

## 8. Event Architecture
- EventBus (in-memory Singleton via `agentcore.bus`)
- Subscribers write to `agent_events` table and log
- Event types: info, warn, error, success, debug
- `bus.agent(emitter, message, status, action, ...)` is the main emit
- Events appear in Agent Activity feed (RightPanel in web via `/api/workspace/events`)
- Cross-service events: **NOT IMPLEMENTED** (single-process only)

## 9. Job Architecture
- Stored in `public.jobs` table
- States: queued → claimed → in_progress → done / failed / blocked / wait_human
- Priority levels (1-100), idempotency keys (used for heartbeat/snapshot/boot), scheduled_for (epoch seconds)
- Polling: 2.5s interval, claimed_at heartbeat updated, jobs older than 1h considered dead and reset
- Max attempts default 2
- Parent job tracking (parent_job_id) for chain tracing
- NO dead-letter queue; failed jobs stay failed

## 10. Memory Architecture
Three layers:
1. **`public.memory` table** — account-scoped long-term memory (role, content, metadata)
2. **`agent/memory.py`** — legacy wrapper, 5 functions: add, recent, context_block, load_grade_feedback, summarize
3. **`agentcore/memory.py`** — thin wrapper, 7 functions, delegates to agent.memory (primarily re-export)
4. **`public.lessons` table** — learned patterns from grading failures
5. **`public.memory_entries` table** — from an older migration, status UNKNOWN (likely unused by v5 workers)

**Gaps:** no embeddings, no semantic search, no vector DB. Memory is keyword/time-based only.

## 11. Knowledge Architecture
- **`knowledge.summarize_day`** agent exists but produces summary stored in memory
- No dedicated knowledge graph, no RAG over past posts beyond recent memory context window
- Brand docs stored in `account_documents` (13 doc types) — fetched into prompts but not chunked/embedded

## 12. Business Plan System
- **13 brand docs** per account: executive_summary, vision_mission, revenue_model, brand_identity, tone_guide, visual_identity, marketing_strategy, instagram_playbook, tiktok_playbook, youtube_playbook, content_calendar, content_rules, hashtags_seo, production_sop
- Generated by architect.py via brand_studio.generate
- Served via `/b/[aid]` page (web) and `/api/business/[aid]`
- **Working**, generated once per account; no regeneration-on-edit yet

## 13. Publishing System
- **Instagram:** `agent/publishing.py:_post_instagram()` — calls Instagram Graph API if IG_USER_ID + IG_ACCESS_TOKEN set; otherwise dry-run receipt
- **YouTube:** `_post_youtube()` — uses `googleapiclient.discovery.build("youtube", "v3", credentials=creds)` if YT_TOKEN_JSON file exists; otherwise dry-run
- **TikTok:** NOT IMPLEMENTED
- **Cross-promotion:** first-comment pin, etc. — stub in distribution.cross_promote
- **Scheduling:** board_items.scheduled_at column exists but no cron job posts at specific times (publishes when render completes)

## 14. Dashboard System
Working pages:
- `/` — landing
- `/login`
- `/dashboard` — overview
- `/dashboard/workspace` — main studio with HumanDesk inline
- `/dashboard/studio` — legacy Studio
- `/dashboard/projects` + nested account routes
- `/dashboard/console` — Developer console (engine picker, provider wallets, settings)
- `/dashboard/models` — AI models catalog (v5.4, **display only — selections saved to settings but not yet used at inference time**)
- `/dashboard/ceo` — CEO scorecard v1 (hardcoded KPI)
- `/dashboard/ceo-v2` — v5.5 CEO Console (working, real data)
- `/dashboard/wallet` — wallet page
- `/dashboard/performance` — placeholder
- `/dashboard/settings` — user settings
- `/dashboard/clone` — viral clone
- `/dashboard/onboarding` — onboarding wizard
- `/b/[aid]` — business plan viewer
- `/studio`, `/trends`, `/proof`, `/wallet` — misc public/marketing

Sidebar shows all sections; human-desk inline; AI provider wallets live on console.

## 15. Analytics System
- `kpi_snapshots` table — hourly metric snapshots by ops.snapshot
- `performance` table — published post views/likes/comments/shares/saves/follows; populated by analytics.collect_metrics (**BUT** no real API call exists to fetch them — placeholder)
- `trend_items` — scouted trends with heat score
- `run_ledger` — every AI spend recorded
- `roi_snapshots` (v5.5) — per-account daily ROI rollup; **revenue hardcoded $0**
- CEO scorecard at `/dashboard/ceo` shows KPI but no charts yet

## 16. Learning System
- **Lessons table** exists; grader feedback stored in memory as grade_feedback
- **Experiments engine**: experiments.create_hook_test + decide (A/B hook tests) — scaffolded
- **Feedback loop:** brain.py loads grade_feedback into prompts (line "grade_feedback" in _fill)
- **Auto prompt evolution:** NOT IMPLEMENTED (planned in Phase 3)

## 17. Security Architecture
- Supabase Auth on all web routes (middleware.ts redirects /login)
- Admin checks via `lib/admin.ts: isAdmin(email)` — hardcoded ADMIN_EMAILS list
- Service role key used server-side only (Vercel + Railway); never exposed to browser
- ROW LEVEL SECURITY: disabled on all pipeline tables (jobs, agent_events, memory, ...); this is intentional for single-tenant MVP
- API keys stored as environment variables, never written to DB
- **No encryption at rest for sensitive data** (Supabase encrypts at infrastructure level, but no app-layer field encryption)
- **No per-user API key isolation yet** (Phase 4 SaaS concern)
- **Risk agent:** risk.scan_content stub — no real content-policy scan yet (no OpenAI moderation / Sightengine / etc.)

## 18. Cost Optimization System
- **Hard budget cap** (ledger.budget_ok) — enforced in legacy tick and multiple workers
- **Kill switch** — settings.kill_switch, checked in workers
- **Auto-throttle** — cfo.preflight delays jobs at 90% budget
- **CEO gate** (v5.5) — per-spend ROI check, reuse-before-generate, cheaper alternatives, account ROI-based model tier selection
- **Free-tier preference** — Gemini free used for images; Groq/OpenRouter free for chat when available
- **Asset reuse** (v5.5) — table exists, ceo._find_reusable runs, **but _store_asset never called after successful publish so library stays empty** — identified gap
- **Cooldown on Gemini** — 10 minute cooldown in visuals._gemini_cooldown
- **Costs recorded** in run_ledger with model/cost_usd/step/provider_label

## 19. Quality Assurance
- **CQO.grade_script** — grader.grade_post() on a 10-point scale with MAX_REWRITES=2
- Grade dimensions: hook, retention, clarity, cta, brand_fit, originality, pacing
- Fail final → item rejected (but v5.3 stopped auto-reject-on-pause)
- No visual QA (no check that rendered video has audio, captions, right duration)
- No post-publish QA (no "did this post actually succeed" webhook validation)

## 20. Testing Coverage
See 09_TEST_COVERAGE.md for detail.
- **Unit tests:** 18 (14 agentcore primitives, 4 worker registration) — all pass
- **Integration tests:** 0
- **E2E tests:** 0
- **CEO gate tests:** 0
- **Publisher tests:** 0
- **Estimated total coverage: ~8%** (well under production-safe threshold)

## 21. Technical Debt
1. **aisuite.py not wired to legacy paths** — 74-model catalog exists but visuals.py, llm.py, brain.py use old direct calls
2. **Post-render handoff missing** — cqo.grade_script doesn't enqueue creative.render
3. **Revenue is hardcoded $0 in roi_snapshots** — all ROI math returns None/zero until real revenue integrated
4. **Asset library never populated** — _store_asset is defined but never called
5. **CEO gate only on write_script** — 5 other spend points (ideate 0.02, render 0.04, tts 0.005, render_video 0.15, brand_studio) not gated
6. **No video generation job** (creative.render_video) despite aisuite.generate_video existing
7. **TikTok publisher missing**
8. **package.json version stuck at 1.4.1**
9. **Web uses inline styles, no design system** (acceptable for MVP, tech debt for scaling)
10. **middleware.ts uses deprecated Next.js convention** (build warning about "proxy" replacement)
11. **No DB migrations framework** (just numbered SQL files, no down/revert, no version runner)
12. **`agent/` legacy package is ~140KB of tangled code with Strangler-Fig wrappers; needs cleanup**
13. **No dead-letter queue for failed jobs**
14. **No retries with backoff in aisuite HTTP calls** beyond generic 3 attempts
15. **Black-bubble fix (theme-fix.ts) has duplicate implementation** (inline script in layout.tsx AND separate import)
16. **provider_balances API calls Anthropic "v1/models" which is cheap but not cached** (hits provider on every Dashboard refresh)

## 22. Known Limitations
- Single active account enforcement (v5 "start with ONE active account")
- No multi-worker horizontal scaling (single Railway process)
- No real-time websockets; events polled
- Video generation is ffmpeg static-image concat only (no AI motion yet)
- Gemini 2.5 Flash Image has rate limits; cooldown protects but can leave frames with procedural fallback only
- No mobile app
- No CDN for media (served from Supabase Storage directly)
- Asset library search is tag/performance-score only — no embeddings/semantic search

## 23. Blockers to profitable production
1. **No real social-API credentials confirmed working for publish+metrics** (IG tokens, YouTube refresh token, TikTok)
2. **No real revenue events** (affiliate click pixel, Stripe webhook for sponsorships, YouTube ad-revenue sync) — so ROI can't be measured
3. **Render handoff gap** (write_script does not enqueue render) — user must verify the reel actually renders end-to-end on Railway
4. **aisuite not wired** — model selection UI is non-functional until legacy paths are migrated
5. **Need at least one real publish (non-dry-run) to confirm end-to-end**

## 24. Risks
| Risk | Severity | Note |
|---|---|---|
| Budget overrun | Medium | Hard cap in place but per-account allocations may double-spend until ceo_decide gates all jobs |
| API key leak | Low | env-only, no DB storage |
| Supabase RLS accidentally enabled | High | Would silently block the service-role-exclusive tables |
| Falcon.ai/Veo3 video quality | Medium | Needs real prompt engineering; likely 2-3 prompt iterations before usable |
| Instagram ban for AI content | Medium | No content policy scanner, no human-in-the-loop approval on all posts yet |
| Single Railway worker crash | Medium | Worker restarts; jobs resume via queued state, but in_progress jobs older than 1h reset |
| Hardcoded AI demo hashtags regressing | Low | Fixed in v5.4; need test |
| CEO gate too aggressive (denying good work) | Medium | Threshold 1.5x may choke cold-start; adjust with data |

## 25. Recommended Next Priorities (in order)
1. **Verify end-to-end pipeline** (script → render → publish → metrics) with one dry-run and one real publish
2. **Wire aisuite into llm.py + visuals.py** so `/dashboard/models` actually controls inference
3. **Add creative.render_video job** calling aisuite.generate_video (fal/kling) with CEO gate
4. **Add ceo_decide gates to the other 5 spend points** (ideate, render, tts, video, brand_studio)
5. **Add _store_asset calls** after successful publish to populate asset library
6. **Wire real revenue events** (affiliate pixel + Stripe webhook) so ROI becomes meaningful
7. **Add TikTok publisher** (largest organic reach for short-form)
8. **Write 30+ integration tests** for critical paths
9. **Fix render enqueue** (cqo → render handoff)
10. **Ship v1 end-to-end profitable post** before adding more agents

---
*Audit concluded. No feature is marked complete without file evidence. Everything not listed in working sections should be assumed NOT IMPLEMENTED until verified.*
