# Agent-X — ROADMAP (rebuilt 2026-07-24, v5.11.19)

Replaces all earlier roadmap versions (previous one archived as
`ROADMAP-v1-archived.md`). Rebuilt by reading the batch history in
`docs/LEDGER.md` end to end, because the append-only request table had
accumulated duplicate rows per ID and could no longer be trusted for status.

**Rule: this file states what is TRUE, not what is hoped.** ✅ means observed
working in production or verified by test against real data. "Shipped but
unproven" is its own state, 🟨, and is not counted as done.

---

## 0. WHERE THE PROGRAM ACTUALLY STANDS

| | |
|---|---|
| Version | v5.11.19 |
| Tests | 270 passing; preflight + boot_check green |
| Worker | healthy; heartbeat now written from the claim loop (structural liveness) |
| Spend | ~$1.34/day (was $2.97 for the same window before the cheap-tier fix) |
| Published | **3 reels rendered — every publish ran `dry-run`. NOTHING HAS EVER POSTED.** |
| Accounts | 2 live (`puppy.parent`, `glowup.daily`), 105 paused |
| Content mix | LIVE — 2 carousels, 2 reels, 5 stories in the last hour |
| Agent grade | ~4.6/10 measured; ~7.0 forecast once shipped-but-unproven items are exercised |

**One sentence:** the engine works end to end and has never published anything,
because platform OAuth does not exist yet.

---

## 1. BLOCKED ON FOUNDER — no engineering can move these

| ID | What | Why it matters |
|---|---|---|
| **REQ-PUB-TOKENS** | Publishing OAuth (IG / TikTok / YouTube) | **THE blocker.** `publish_in`/`publish_ti`/`publish_yo` run `dry-run`. Publisher is stuck at 1/10. Engagement data, the survival loop and pricing evidence are all gated on this. |
| **REQ-KEYROTATE-1** | Rotate the Groq key exposed in a screenshot | Groq is the healthiest free rung (0 x 429). A leaked key is a live risk. |
| **REQ-TOKEN-ROTATE-2** | Rotate the two `axmcp_` tokens pasted in chat | Settings -> MCP. |
| **REQ-COMPETITORS** | Give 5-10 real handles (pets, skincare) | I cannot scrape Instagram — ToS, and it contradicts the honesty policy. Curated seeds beat a scraped list. |

---

## 2. AWAITING FOUNDER DECISION

| ID | Question | Recommendation |
|---|---|---|
| **REQ-AGENT-PURPOSE** | `cto`, `strategist`, `planner`, `analyst` run and produce nothing measurable | Retire `cto` + `analyst`; give `planner` the format-mix job and `strategist` the niche-angle job |
| **REQ-STUDIO-CONSOLE** | In-site manual creation console | AGAINST the broad version (rebuilds OpenArt, contradicts the autonomy moat). FOR a narrow "fix this draft" panel |
| **REQ-TRADEMARK** | "Agent-X" vs agentx.so | Resolve before public marketing |
| **REQ-MCP-CLAIMS** | Public description of MCP integration | Honest scope: reads the platform, queues/approves. Not "AI that runs your business" |
| **REQ-HEYGEN** | Avatar video | NO — $1-5/min against a $2/day price; faceless needs no presenter |

---

## 3. SHIPPED BUT UNPROVEN — verify before building further

Deployed and tested; NOT yet observed working on real content.

| ID | What | How to verify |
|---|---|---|
| **REQ-VISUALS-REAL** | Free keyless image rung before gradient fallback | Approve a reel; `settings.visuals_health.gradient_frames` must stay 0 and ledger must show `pollinations-free` |
| **REQ-ART-SUBJECT** | Art Director names photographable scenes per niche | Watch for `art_start`, then real subjects in frame prompts |
| **REQ-IDEOGRAM** | Ideogram endpoint implemented + `text_heavy` tier | Render a carousel; ledger should show `ideogram-v3` |
| **REQ-RENDER-MEMORY** | zoompan 1296x2304 -> 1188x2112, ffmpeg `-threads 1` | A reel renders without the worker restarting |
| **REQ-DUP-HOOK** | Hook and CTA spoken once | Listen to the next reel's opening and closing |
| **REQ-REWRITE-NOT-REJECT** | Grader parks instead of discarding | `cqo_to_human` events appear; grader stops adding to `rejected` |
| **REQ-JSON-REPAIR** | Near-valid model JSON repaired | Carousel writes stop failing on `Expecting value:` |
| **REQ-MCP-EXACT-COUNTS** | Connector counts exact | Re-add connector, run `agentx_pipeline_state`; `jobs done` ~40,000+, not 987 |

---

## 4. OPEN ENGINEERING — priority order

### Phase A — before a 5-day content run

| ID | What | Size | Why now |
|---|---|---|---|
| **REQ-PUBLISH-HONESTY** | Stop marking items `published` when publish ran dry-run | 1 pt | The board lies today; every metric built on it is unreliable |
| **REQ-LADDER-ORDER** | Promote Groq above Gemini in the free text ladder | 1 pt | Groq 0 x 429; Gemini 7 x 429 penalised; OpenRouter 30 x 429. Healthiest rung is not first |
| **REQ-STORY-VERIFY** | Confirm `write_story` completes end to end | 1 pt | 7 story briefs created, no `story_done` observed |
| **REQ-CAROUSEL-VERIFY** | Confirm carousel renders + uploads slides | 1 pt | One carousel failed on JSON; repair unproven |

### Phase B — quality and learning

| ID | What | Size |
|---|---|---|
| **REQ-SKILL-PROMPTS** | Adapt 3 public repos into `pipeline/skills/` (media playbooks -> `creative/`, humanizer -> `cqo/`, hooks -> `creative/`) | 3 pt |
| **REQ-LEARN-1** | Replace the 45-min SLA heuristic with measured p75 | 2 pt |
| **REQ-PREP-REDESIGN** | Paused-account prep: subordinate, capped, decay-classified, graded | 3 pt |
| **REQ-PREP-PROMOTE** | On resume, promote banked prep into the live funnel | 2 pt |
| **REQ-DEADCODE-1** | Delete `pipeline/agent/orchestrator.py` + legacy modules; refresh `docs/AGENTS_ROSTER.md` | 2 pt |

### Phase C — scale (pointless below ~10 accounts)

| ID | What | Size |
|---|---|---|
| **REQ-ISOLATION-1** | Per-account queues + leases | 5 pt |
| **REQ-CIRCUIT-ACCT** | Per-account circuit breakers | 3 pt |
| **REQ-SCALE-WORKERS** | 2nd Railway worker replica | 2 pt |
| **REQ-RENDER-REGION** | Multi-region render capacity | 5 pt |
| **REQ-ONBOARD-AUTO** | Automated brand onboarding | 5 pt |
| **REQ-MODEL-NICHE** | Learned per-niche model selection | 3 pt |
| **REQ-BUDGET-2** | Per-account monthly cap + spend bar in UI | 2 pt |
| **REQ-SLA-UI** | SLA chips + prep filter in Studio | 2 pt |
| **REQ-WEB-404** | `/dashboard/store`, `/digital`, `/affiliate` 404 | 1 pt |

### Phase D — revenue

| ID | What | Size |
|---|---|---|
| **REQ-PAYOUT-1** | Stripe Connect payout automation (50% affiliate) | 5 pt |
| **REQ-SURVIVAL-1** | Close the economic loop: revenue -> account budget -> model tier -> pause. Automaton-style but honest: agents do not self-improve; the SYSTEM self-regulates | 8 pt |

---

## 5. STANDING RULES — do not drop

1. **Ledger is append-only.** §1B request tracker, §2 decision log. Never rewrite.
2. **Every response ends with an Instruction Verification Report** — nothing silently dropped.
3. **Gates before packaging:** `py_compile` per module, `pytest` (270), `preflight.py`,
   `boot_check.py`, isolated `tsc` for web. Red means do not ship.
4. **`web/version.json` is the ONE version constant** — Python and web both read it.
5. **A swallowed exception is a silent feature deletion.** Four production faults from
   this pattern: gradient fallback logging `ok=True`; `_public_url` returning `None`;
   the `_dt` NameError that disabled the entire content mix; `Priority.MEDIUM` that made
   carousels impossible. When adding `try/except`, decide explicitly whether it must be loud.
6. **Never claim self-improvement.** No weights change. Prompts, skills, memory lessons and
   founder feedback improve — all measurable via `ops.scorecard`, which may return
   "flat" or "regressing".
