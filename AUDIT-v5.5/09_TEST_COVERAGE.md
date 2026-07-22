# Test Coverage Report (v5.5)

## Summary
- **Total test files:** 2
- **Total tests:** 18 (100% pass rate last run)
- **Unit test coverage:** ~15% of core agentcore primitives
- **Integration test coverage:** 0%
- **End-to-end coverage:** 0%
- **Estimated overall coverage: ~8%**

## Existing tests

### `pipeline/tests/test_core.py` (14 tests)
Tests for v4.4 agentcore primitives (pre-worker):
1. Models: Job creation, priority, serialization
2. Events: Bus subscribe/publish, EventType
3. Worker: register handlers, dispatch, retry
4. Jobs: Postgres queue enqueue/claim/complete basics (mocked)
5. Guards: Circuit breaker trip/reset
6. Observability: Span start/end
7. Config: get/set env
8. Memory stub
9. Ledger: record, budget_ok, spent_today (uses stub supabase)
10. Validators
11. Priority ordering
12. Idempotency keys
13. Error classification (Retryable vs Fatal)
14. Max attempts logic

**Status:** PASSING. Covers basics but uses a stub Supabase client; does NOT test against real schema.

### `pipeline/tests/test_v5_worker.py` (4 tests)
1. Worker imports cleanly
2. register_all imports all 16 departments
3. Job serialization to dict
4. Worker dispatch for a dummy registered job

**Status:** PASSING. Smoke-tests only.

## Missing critical tests (P0)
1. **CEO gate tests** — verify approve/deny/reuse/delay/cheaper decisions under various ROI scenarios
2. **Niche hashtag tests** — verify pet account doesn't get #ai tags, finance gets finance tags, etc. (regression for the v5.4 bug)
3. **Pause/resume tests** — verify pausing sets jobs=blocked not rejected; verify resume clears rejects
4. **Budget cap tests** — verify hard cap at daily_budget_usd prevents overspend
5. **aisuite.generate_text** fallback tests across providers
6. **aisuite.generate_image** calls correct endpoint per provider
7. **Ledger provider_label inference** from model string
8. **Brand_studio document generation** produces valid 13 doc structure

## Missing integration tests (P1)
1. **End-to-end content pipeline**: ideate → write_script (CEO gated) → grade → render → publish (dry-run)
2. **Worker queue idempotency**: multiple enqueues of same idempotency key don't produce duplicates
3. **Stuck-job repair**: SQL repair resets claimed >1h
4. **Scout niche filtering**: pet account doesn't see AI trends
5. **Capital allocation math**: ROI > 3x scales, 3-day losing streak pauses
6. **Asset reuse**: existing asset in library short-circuits LLM call
7. **Web API routes**: `/api/providers/balance`, `/api/ai-models`, `/api/ceo-decisions` return expected shape
8. **SQL migration idempotency**: running v5.5_PRODUCTION.sql twice produces no errors

## Missing end-to-end tests (P2)
1. Deploy worker to Railway, verify 68 modules boot cleanly in production
2. Connect real IG sandbox account, publish one dry-run reel, verify receipt
3. Real $1 spend test: run for a day, verify ledger total ≤ budget
4. Pause mid-production, verify no new posts generated
5. Cross-account isolation: cat content doesn't leak to finance account

## Critical regressions not covered by tests
- [ ] AI hashtags leaking to non-AI niches (the bug that triggered v5.4)
- [ ] Pause/reject cascade (v5.3 bug)
- [ ] SQL migration ordering (jobs-must-exist-before-index bug)
- [ ] Over-budget spending (the $6.50 on $3.00 bug)
- [ ] Theme/black-bubble CSS
- [ ] CEO gate bypass (non-gated jobs spending without approval)
- [ ] aisuite model selection not honored (UI picks model but legacy llm.py ignores it)
- [ ] Creative render not enqueued after grade pass (the gap I identified in audit)

## Estimated effort to reach production-safe coverage
- **P0 tests:** 8-12 hours (50-80 unit tests for core gates)
- **P1 tests:** 16-24 hours (integration harness with test Postgres, fixtures for board_items/accounts)
- **P2 tests:** 1-2 weeks (staging environment, test social accounts, real money tests)
- **Target coverage for v6 SaaS launch:** 60%+ unit, 40%+ integration

## How to run existing tests
```bash
cd pipeline
python -m pytest tests/ -v
```
Result: 18 passed in 0.21s.

## Recommendations
1. Add P0 tests BEFORE wiring aisuite into legacy paths — any router change risks silent fallbacks
2. Add a SQL migration dry-run test (spin up ephemeral Postgres, run migrations in order)
3. Add a `tests/integration/` directory and a conftest.py with ephemeral Postgres + stubbed HTTP
4. Wire tests into CI (GitHub Actions) on every push
5. Don't ship video generation (creative.render_video) without integration tests — it costs $0.15-0.50 per call and failures burn cash fast
