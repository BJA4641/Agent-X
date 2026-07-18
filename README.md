# BuildAlong — monorepo

One system, three parts:

| Dir | What | Deploys to |
|---|---|---|
| `web/` | Next.js site (landing, auth, dashboard, Stripe, waitlist) | **Vercel** |
| `pipeline/` | Python content worker (script→voice→visuals→video→board→publish) | **Railway / any always-on box** (NOT Vercel) |
| `db/schema.sql` | Single canonical Postgres schema (board + web + ledger) | **Supabase SQL editor** |
| `prompts/` | Versioned prompts (version stamped into every run-ledger row) | ships with pipeline |

Read `docs/DEPLOY.md` for the exact order. Quickstart (no keys, runs in demo mode):

```bash
cd pipeline && pip install -r requirements.txt
python cli.py status          # what's live vs dry-run
python cli.py tick --stub     # full loop: plan → draft → (your approval) → publish → report
python cli.py generate "3 AI tools every creator should steal"   # one real video
```

## Safety rails built in
- **Kill switch:** set `KILL_SWITCH=1` in env (or create a file named `STOP` in pipeline/) — every tick refuses to run.
- **Budget cap:** `DAILY_BUDGET_USD` — the ledger sums today's spend before any paid call; over budget = skip, log, continue free paths.
- **Idempotent publishing:** every publish carries a deterministic key; a receipt on the item means it will never double-post.
- **Run ledger:** every LLM/image/publish call is a row (cost, model, prompt version). This later becomes SaaS metering.
