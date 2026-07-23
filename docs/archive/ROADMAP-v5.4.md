# Agent-X v5.4 Roadmap & Changelog

**Date:** 2026-07-20
**Author:** AI co-pilot (Claude Sonnet 4.5 via Arena.ai)
**Current schema version:** v5.4 (`settings.key = 'schema_version'`)

---

## ✅ COMPLETED — v5.3 & v5.4

### Phase 1 — Business Blueprint (previously done)
- 11 business-plan documents
- Niche/angle/clone playbooks
- Cost targets: reels $0.03-0.06, image $0.02-0.04, gallery $0.13-0.25
- 5x cost pricing model for SaaS

### v5.0 → v5.3 — Worker Engine & Critical Bug Fixes

| # | Fix / Feature | What changed | AI module used |
|---|---|---|---|
| 1 | Event-driven worker engine | 27 job types across 14 departments (CFO, CQO, research, editorial, creative, postprod, distribution, analytics, ops, knowledge, risk, human_desk, brand_studio, monetization) | Claude Sonnet 4.5 (architecture) + Gemini 2.5 Flash (iterations) |
| 2 | SQL ordering bug fixed | CREATE TABLE runs before ALTER/CREATE INDEX — fixed `relation "public.jobs" does not exist` | Claude Sonnet 4.5 |
| 3 | Pause/Resume bug | Pressing "Stop work" no longer auto-rejects ideas; in-flight jobs move to `blocked`, board_items stay put | Claude Sonnet 4.5 |
| 4 | Niche awareness fixed | Topics, hashtags, visuals, captions all filtered by account niche (pets/cats/dogs/fitness/finance/cooking/beauty/gaming/travel + ai default) | Claude Sonnet 4.5 |
| 5 | Wallet live spend | `/api/wallet` reads `run_ledger` (real pipeline spend) not demo topups | Claude Sonnet 4.5 |
| 6 | Hard budget cap | Pre-checks in legacy `orchestrator.tick()` + worker ideate/write_script/render; auto-throttle with reserve fraction | Claude Sonnet 4.5 |
| 7 | Black chat bubble fix | `theme-fix.ts` injected in `<head>` before first paint (previously file existed but wasn't imported) | Claude Sonnet 4.5 |
| 8 | Business plan page | `/b/[aid]` — all 13 brand docs + inline video player for rendered posts | Claude Sonnet 4.5 |
| 9 | Brand tone vs identity | Warning shown on /b page when they match | Claude Sonnet 4.5 |
| 10 | Cross-project business access | `/api/business/[aid]` checks ownership, supports admin view across projects | Claude Sonnet 4.5 |
| 11 | Auto-fallback toggle | Green banner in Developer console; toggleable ON/OFF; saved to DB; respected by worker | Claude Sonnet 4.5 |
| 12 | AI Provider Wallets panel | Live balance check for Anthropic/Gemini/OpenRouter/Groq/Railway/ElevenLabs; MTD spend per provider; last-used timestamp | Claude Sonnet 4.5 |
| 13 | SQL repair for auto-rejects | Items rejected with no human reason reset to 'idea'; stale AI-hashtag scripts wiped for re-generation | Claude Sonnet 4.5 |
| 14 | `provider_label` + `cost_cents` on `run_ledger` | Ledger now records which provider was used + dollar-cents cost; powers accurate per-provider spend | Claude Sonnet 4.5 |

### v5.4 — Expanded AI Provider Catalog (this chat)

| # | Feature | Details | AI module used |
|---|---|---|---|
| 15 | **74 models across 7 categories** | Text (19), Text→Image (16), Image→Image (6), Text→Video (12), Image→Video (9), Voice/TTS (7), Video edit (5) — all listed in `pipeline/agentcore/providers_catalog.json` | Claude Sonnet 4.5 (research + code) |
| 16 | `aisuite.py` — unified provider router | One dispatcher: `generate_text()`, `generate_image()`, `edit_image()`, `tts()`, `generate_video()`. Auto-fallback within category; free tiers last so $0 when possible | Claude Sonnet 4.5 |
| 17 | `/dashboard/models` admin page | 7 category tabs, LIVE/FREE/NO KEY badges, arena rank, cost/use, one-click "Use this" default switch | Claude Sonnet 4.5 |
| 18 | `/api/ai-models` API | GET catalog + chosen defaults; POST to set default per category; checks env vars to compute has_key | Claude Sonnet 4.5 |
| 19 | Per-category model settings DB rows | `settings.model_t2i`, `model_t2v`, `model_i2v`, `model_ie`, `model_tts`, `model_vedit` — chosen defaults persist | Claude Sonnet 4.5 |
| 20 | **Pet-post hashtag bug root-caused + fixed** | `_DEMO_SCRIPT` was hardcoded AI content (fired on LLM failure/budget-kill); replaced with niche-neutral fallback; hashtag/visual/caption dictionaries for 11 niches; scout now niche-filters trends | Claude Sonnet 4.5 (debugged from your screenshot) |
| 21 | Boot check green | 68 modules import cleanly | — |
| 22 | 18/18 unit tests pass | agentcore (14) + v5 worker (4) | — |
| 23 | Vercel build passes | `next build` compiles all pages & routes | — |

---

## 🧭 PENDING ROADMAP (next up — requires "CONTINUE")

### Immediate (blocking production revenue)
| P# | Item | Notes |
|---|---|---|
| P1 | **Wire `aisuite.py` into all legacy paths** | Currently the new aisuite router is written but visuals.py/brain.py still call Gemini directly. Needs 1-2 hours to swap image/TTS calls to go through `aisuite.generate_image()` / `aisuite.tts()` so model selection from `/dashboard/models` actually works at runtime. The UI and catalog are live; the worker still uses legacy paths in this v5.4 drop. |
| P2 | **Add video generation pipeline job** | `creative.render_video` job that calls `aisuite.generate_video()` for TTV/ITV using Fal keys; currently videos aren't generated at all (frames → ffmpeg only, no AI video). This is the biggest missing production feature. |
| P3 | **Verify stop-work actually blocks all in-flight** | Integration test with pause → trigger job → confirm no rejection; the DB patch is done but hasn't been live-tested with real Railway worker |
| P4 | **Spend dashboard over-budget bug ($6.503/$3.00)** | v5.4 pre-checks budget before starting jobs but ledger already had $6.50 of old spend from before the cap; fresh-day ledger should respect cap. Add a realtime "spend vs cap" gauge on Wallet panel |
| P5 | **Deploy confirmation** | User (jadaridi8) needs to push v5.4 zip, run v5.4_PRODUCTION.sql, add `FAL_KEY`, confirm cat posts come out with #cats tags, confirm `/dashboard/models` shows LIVE badges |

### Short term (next phase, v5.5)
| P# | Item |
|---|---|
| P6 | **Auto-caption burn-in word-by-word** (Kinetic typography like Alex Hormozi / Devin Jatho style) — current captions are simple ASS; need high-contrast, color-pop, per-word timing |
| P7 | **Human-desk approve/reject UI wiring** — buttons exist but need to confirm resolution propagates to jobs; inline workspace widget polish |
| P8 | **Affiliate link rotation + sponsor-deal inbox** — rotate offers per post; scan email for sponsor deals |
| P9 | **CEO scorecard trend charts** from kpi_snapshots (data is being collected; charts not built) |
| P10 | **Studio post thumbnails/preview** in console/workspace pages |
| P11 | **Multi-Railway-service split** — separate scout/render/publish workers so render doesn't block scriptwriting |
| P12 | **Prompt-evolution loop** (lessons → prompt tweaks → A/B compare) |
| P13 | **First-post publishing test** — connect one IG/TikTok account, publish 3 posts end-to-end, watch KPIs |

### Medium term (v6 — SaaS revenue)
| P# | Item |
|---|---|
| P14 | User-facing credits system (Stripe checkout already sketched) |
| P15 | Multi-tenant isolation / RLS enforcement (RLS currently off; enable after testing) |
| P16 | OAuth social-connect UI (IG, TikTok, YouTube, X) — users connect their own accounts |
| P17 | Public waitlist → signup → onboarding flow tightening |
| P18 | Email notifications (human desk needs approval, publish success/fail, wallet low) |
| P19 | Affiliate program for referrers |

### Long term (v7+ — autonomous media empire)
| P# | Item |
|---|---|
| P20 | 100+ accounts running concurrently with per-account budgets |
| P21 | Automated sponsorship outreach via cold-email/LinkedIn agents |
| P22 | Digital product generation (e-books, courses) auto-built from top-performing content |
| P23 | White-label / agency tier (let others run Agent-X instances) |
| P24 | Multi-language content (Spanish, Portuguese, Arabic — high-ROI markets) |

---

## 📂 Codebase map (v5.4)

```
Agent-X/
├── db/
│   ├── v5.4_PRODUCTION.sql   ← RUN THIS IN SUPABASE
│   └── (previous migrations)
├── pipeline/
│   ├── Dockerfile            ← CMD python cli.py worker
│   ├── cli.py                ← worker / loop / demo / tick
│   ├── boot_check.py         ← 68-module import check
│   ├── agent/                ← v4.3 "legacy" modules (strangler-fig wrapped by v5 workers)
│   │   ├── llm.py            ← chat() with auto-fallback (Anthropic→Gemini→Groq→OpenRouter)
│   │   ├── brain.py          ← v5.4 PATCHED: niche-aware hashtags/visuals/captions
│   │   ├── scout.py          ← v5.4 PATCHED: niche-filtered trend fetch
│   │   ├── visuals.py        ← frames: Gemini images + procedural composites
│   │   ├── architect.py      ← generates 13 brand docs
│   │   └── (composer, grader, orchestrator, board, memory, ...)
│   └── agentcore/            ← v5 primitives
│       ├── aisuite.py        ← 🆕 v5.4: unified router for ALL 74 AI models
│       ├── providers_catalog.json ← 🆕 v5.4: catalog of 74 models across 7 categories
│       ├── worker.py, jobs.py, bus.py
│       ├── llm.py            ← ModelRouter tier routing
│       ├── ledger.py         ← v5.4 PATCHED: provider_label + cost_cents
│       ├── guards.py (circuit breakers)
│       └── (config, models, events, memory, observability, runtime, validators)
├── workers/departments/      ← v5 job handlers
│   ├── finance.py (CFO preflight), cqo.py (quality gate), risk.py
│   ├── portfolio.py, research.py, editorial.py, creative.py
│   ├── postprod.py, distribution.py, analytics.py, ops.py
│   ├── knowledge.py, human_desk.py, experiments.py
│   ├── brand_studio.py, monetization.py
│   └── common.py             ← v5.4: hard_budget_ok, account_daily_budget, active_accounts
└── web/
    ├── app/
    │   ├── api/
    │   │   ├── ai-models/route.ts        ← 🆕 v5.4: catalog + set-default
    │   │   ├── providers/balance/route.ts ← live provider wallet balances
    │   │   ├── studio/route.ts           ← v5.4 PATCHED: set_autofallback action
    │   │   ├── business/[aid]/route.ts   ← brand docs for /b page
    │   │   ├── projects/[pid]/accounts/[aid]/route.ts ← pause/resume fix
    │   │   ├── wallet/route.ts           ← real spend from run_ledger
    │   │   └── (ceo, human, workers, ...)
    │   ├── b/[aid]/page.tsx              ← business plan per account
    │   ├── dashboard/
    │   │   ├── models/page.tsx           ← 🆕 v5.4: AI models admin page
    │   │   ├── console/page.tsx          ← developer console (v5.4 adds ProviderBalances)
    │   │   ├── ceo/page.tsx              ← CEO scorecard
    │   │   └── (workspace, wallet, performance, ...)
    │   └── layout.tsx                    ← v5.4 PATCHED: black-bubble fix in <head>
    └── components/
        ├── SettingsPanel.tsx             ← v5.4: auto-fallback banner
        ├── ProviderBalances.tsx          ← 🆕 v5.4: live wallet panel
        ├── Sidebar.tsx, HumanDesk.tsx
        └── (AdminActions, StudioBoard, ...)
```

---

## 🔑 Environment Variables (complete reference)

Required (already set):
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `TENANT_ID=me`, `DAILY_BUDGET_USD=1.50`

Unlock 20+ models with ONE key (Priority #1):
`FAL_KEY` ← fal.ai signup, $5 free credit

Best image + Sora (Priority #2):
`OPENAI_API_KEY`

Free fallbacks (5 min total, Priority #3):
`GROQ_API_KEY`, `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`

Image quality upgrades (Priority #4):
`BFL_API_KEY`, `IDEOGRAM_API_KEY`, `STABILITY_API_KEY`, `RECRAFT_API_KEY`, `GOAPI_KEY`

Chat expansion (Priority #5):
`XAI_API_KEY`, `MISTRAL_API_KEY`, `TOGETHER_API_KEY`, `FIREWORKS_API_KEY`, `COHERE_API_KEY`

Voice (Priority #6):
`ELEVENLABS_API_KEY`, `CARTESIA_API_KEY`, `DEEPGRAM_API_KEY`, `PLAYHT_API_KEY`

Monitoring:
`RAILWAY_API_TOKEN`

Full step-by-step signups with direct URLs: see `API-KEYS-TODO.txt`.

---

## 🤖 AI authorship note

Every code change in v5.3 and v5.4 was written by **Claude Sonnet 4.5** (Anthropic, July 2025 version) running on Arena.ai Agent Mode. The model was used because:
- It's one of the strongest for full-stack TypeScript + Python + SQL refactoring
- 200k context window allowed it to hold the whole codebase in one conversation
- It was already the default provider in ANTHROPIC_API_KEY

Research for the AI model rankings was done via web search (Artificial Analysis LM Arena, wavespeed.ai, tech-insider.org rankings July 2026), then cross-referenced into the catalog.

When a syntax bug appeared (the `}` typo in `/api/providers/balance/route.ts` line 153), `npx next build` surfaced it and Claude fixed it in one shot.

---

## ▶️ Next action for CEO (you)

1. Run `db/v5.4_PRODUCTION.sql` in Supabase SQL Editor
2. Push the v5.4 upgrade zip to GitHub → Vercel + Railway redeploy
3. Spend 10 minutes signing up for the 5 minimum-viable keys (see `API-KEYS-TODO.txt`)
4. Open `/dashboard/models` and confirm LIVE badges appear
5. Resume the Pet Rescue account; wait 5 minutes for a new script to generate; confirm hashtags are `#catsoftiktok #petrescue` NOT `#ai #tech`
6. When confirmed, reply **"CONTINUE"** and we tackle P1 (wire aisuite into legacy paths) + P2 (video generation)

**Production success rate > volume.** One working, profitable pet account beats 73 failures.
