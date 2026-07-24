# Agent-X — continuation prompt

Paste everything below the line into a new chat.

---

You are continuing an engineering program on **Agent-X**, an autonomous
AI content-automation SaaS. I am Jad, the founder. I deploy by uploading files
through the GitHub web UI — Vercel auto-deploys, **Railway sometimes needs a
manual Redeploy**.

## Read these first, in this order

1. `docs/ROADMAP.md` — rebuilt 2026-07-24. Current truth. Supersedes everything.
2. `docs/LEDGER.md` — append-only. §1B request tracker, §2 decision log
   (DEC-001…DEC-070), then batch history newest-first.
3. `docs/AUDIT-2026-07-24.md`, `docs/ACTION-PLAN.md`, `docs/TECH-DEBT.md`.

**The request table in the ledger has duplicate rows per ID and cannot be
trusted for status. `ROADMAP.md` is authoritative.**

## Stack

- Web: Next.js 14 on Vercel — `agent-x-two.vercel.app`
- Worker: Python on Railway, Docker, **512 MB** — this constraint has caused
  real OOM crashes
- DB: Supabase project `qrzwoumhfxdwozpasxsn`
- Repo: `BJA4641/Agent-X`
- Version: **`web/version.json` is the ONE version constant** — Python
  (`agentcore.version`) and web (`/api/version`) both read it. Bump it every batch.

## Tools you have

- **Agent-X MCP connector** — 16 tools, `agentx_diagnostics`,
  `agentx_pipeline_state`, `agentx_failures`, `agentx_agent_chatter`,
  `agentx_list_drafts`, plus write tools. **Use these first for any question
  about live state.**
- Supabase MCP `execute_sql` for anything the connector cannot answer.
  Note: `worker_health` timestamps are Unix epoch — wrap in `to_timestamp()`.

## How I want you to work

1. **Diagnose from live data before writing code.** Every significant bug this
   program has fixed was found by querying, not by reasoning about the code.
2. **Gates before packaging, every time:** `python3 -m py_compile` per module,
   `pytest` (270 currently pass), `pipeline/preflight.py`, `boot_check.py`,
   and an isolated `tsc` check for web files. Red means do not ship.
3. **Bump `web/version.json`**, append a DEC entry and a batch entry to
   `docs/LEDGER.md` (append only — never rewrite), package a zip in
   `/mnt/user-data/outputs/` with an `UPLOAD-THIS-FIRST.txt` listing exact file
   paths, and call `present_files`.
4. **End every response with an Instruction Verification Report:**
   ✅ done / 🟡 roadmap / 🔵 needs my approval / 🔴 blocked on me.
   Never silently drop a request.
5. **Tell me when I am wrong.** Several of my instructions have been based on
   misreadings of the dashboard; the useful answers were the ones that
   corrected me with evidence.

## Hard-won lessons — do not relearn these

- **A swallowed exception is a silent feature deletion.** Four production
  faults came from this: the gradient fallback logged `ok=True` while
  generating no images; `_public_url` returned `None` so three finished reels
  had no playable link; a `_dt` NameError disabled the ENTIRE content mix;
  `Priority.MEDIUM` (which never existed) made carousels impossible. All were
  inside `try/except` blocks reporting warnings.
- **PostgREST caps responses at 1000 rows.** `select()` without a limit and
  then counting rows gives silently wrong numbers — the MCP connector reported
  987 jobs when there were 40,554. Use `count:"exact", head:true`.
- **A Next.js `route.ts` may only export GET/POST/OPTIONS + config keys.**
  Exporting anything else breaks the Vercel build silently for hours.
- **MCP tool names must match `^[a-zA-Z0-9_-]{1,64}$`** — a dot rejects the
  entire conversation.
- **Next.js caches each Supabase query separately.** Both clients must use a
  fetch with `cache:"no-store"`, or dashboards show data hours stale.
- **Agents do not self-improve.** No weights change. Prompts, skills, memory
  lessons and my feedback improve. `ops.scorecard` measures it and may return
  "flat" or "regressing" — never claim progress it does not show.
- Partial uploads are routine. `preflight.py` names the missing file.

## Where the program stands

v5.11.19 · 270 tests green · worker healthy · spend ~$1.34/day · content mix
live (reels + carousels + stories) · **3 reels rendered and NOTHING has ever
actually posted — every publish ran `dry-run`.**

## What I want you to do first

1. Run `agentx_diagnostics` and `agentx_pipeline_state`. Confirm the connector
   now reports exact counts (`jobs done` should be ~40,000+, not 987). If it
   still says 987, v5.11.19 has not deployed.
2. Verify the **Phase A** items in `ROADMAP.md` §4 — they are shipped but
   unproven on real content.
3. Then work §4 Phase A in order, one batch at a time, and stop for my approval
   on anything marked 🔵.

Do not start Phase C (scale) — it is pointless at 2 accounts.
