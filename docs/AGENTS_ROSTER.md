# Agent-X — Production Agent Roster (v5.9.4)

> **This file replaces the old 18-agent roster.** That document described the
> legacy `pipeline/agent/` orchestrator, which is **no longer deployed**. It is
> kept in the repo only as fallback code, reachable via `python cli.py loop`.

## What actually runs in production

Railway runs `python cli.py worker` (see `pipeline/Dockerfile`), which boots the
**agentcore runtime** (`pipeline/agentcore/`) — a single-process, event-driven,
job-queue worker — and registers **19 departments** from
`pipeline/workers/departments/`. Version string lives in
`pipeline/workers/runner.py` (`VERSION = "5.9.4"`).

Jobs flow through the `jobs` table in Supabase (epoch timestamps — cast with
`to_timestamp()`). Every heartbeat updates `worker_health`. Every spend is
written to `run_ledger` and gated by the CEO + Finance departments.

## The 19 departments (registration order)

| # | Department | Module | Role |
|---|-----------|--------|------|
| 1 | **Finance (CFO)** | `finance.py` | Budget caps, spend approval, wallet enforcement |
| 2 | **CQO (Quality)** | `cqo.py` | Quality gate on every draft; grading + ship-best ≥7.0 rule |
| 3 | **Risk** | `risk.py` | Claim safety, policy compliance, risk register |
| 4 | **CEO** | `ceo.py` | Autonomous CEO engine — gates every spend decision, $25/mo per-account hard cap |
| 5 | **Brand Studio** | `brand_studio.py` | Brand documents (13-doc business plan per account) |
| 6 | **Portfolio** | `portfolio.py` | Multi-account portfolio management + main tick loop |
| 7 | **Research** | `research.py` | Niche keywords, competitor angles, audience questions |
| 8 | **Editorial** | `editorial.py` | Scripts, hooks, captions |
| 9 | **Creative** | `creative.py` | Visual frames, image generation |
| 10 | **Post-Production** | `postprod.py` | Video assembly (ffmpeg), captions burn, audio mix |
| 11 | **Monetization** | `monetization.py` | Affiliate placement, CTA strategy, revenue events |
| 12 | **Distribution** | `distribution.py` | Publishing / cross-posting / scheduling |
| 13 | **Analytics** | `analytics.py` | Metrics pull + post-mortems |
| 14 | **Knowledge** | `knowledge.py` | Memory + lessons loop |
| 15 | **Ops (Infra)** | `ops.py` | Heartbeats, autothrottle, health, retries |
| 16 | **Human Desk** | `human_desk.py` | Founder approvals + escalations (`escalations` table) |
| 17 | **Experiments** | `experiments.py` | A/B experiment engine (`experiments` table) |
| 18 | **Providers** | `providers.py` | API key probe: liveness + balances on boot (v5.8.7) |
| 19 | **Strategy** | `strategy.py` | 10-day paid audit + arena leaderboard model scout (v5.8.8) |

## Governance chain per post
Editorial draft → CQO grade (ship-best ≥7.0) → Risk check → CEO spend approval
→ Creative/Post-Production render → Distribution publish → Analytics post-mortem
→ Knowledge lesson. Finance meters every step into `run_ledger`.

## Legacy code (do not document as live)
`pipeline/agent/*` (orchestrator.py, brain.py, scout.py, etc.) is the pre-v5
single-loop system. It shares some tables but is not started by the Dockerfile.
Treat it as dead code pending deletion.
