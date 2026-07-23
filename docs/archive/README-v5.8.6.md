# Agent-X v5.8.6 — FREE-FIRST ROUTING (Anthropic = final audit only)

## Why
On 2026-07-23 the worker spent **$1.14 on Claude and produced zero content**.
Breakdown: aisuite.text 24 calls/$0.57 · brain (writer) 12/$0.41 · grader 12/$0.16.
The free-model council existed since v5.8.2 — but three leaks routed work to Claude anyway.

## The three leaks, and the fixes

**1. GEMINI_API_KEY is not set in Railway.**
`council._providers()` filters `_FREE_ORDER` by `llm._has_key(p)`. No key = Gemini is
skipped entirely. That is why Gemini shows **0 calls** despite the free tier. Only
groq + openrouter were live, and both rate-limited today.
→ **Action for you (not code): add GEMINI_API_KEY in Railway Variables.**
   Free key: https://aistudio.google.com/apikey — this alone stops most of the burn.

**2. Writer fell back to paid.** `brain.py` called `council.debate_or_chat()`, whose
last resort is the paid `llm.chat()`. When groq/openrouter rate-limited, every script
silently went to Claude ($0.41).
→ Now calls `council.debate()` directly. No free model = the job raises, delays and
   retries when free models are back. Set `ALLOW_PAID_WRITER=1` to restore old behaviour.

**3. Grader was Claude by default.** `grader.grade_post()` used `llm.chat()` → aisuite
`standard` tier → catalog listed **claude-sonnet-4-5 first** ($0.16 + the $0.57 of
aisuite.text calls). Rewrites did the same.
→ Grading and rewrites now use `council.free_chat()`. Paid grading only with
   `ALLOW_PAID_GRADER=1`; otherwise the draft is parked honestly as UNGRADED.

## Anthropic's new and only job: the final audit
`cqo._claude_final_audit()` runs **one** Claude call per item, at the moment a script is
about to ship (either a clean pass or a v5.8.5 ship-best). Free models write, debate and
grade every attempt; Claude verifies the winner.

- Claude agrees → render.
- Claude scores below 7.0 → item parked as `drafted` with audit notes for you (no render spend).
- No ANTHROPIC key, audit switched off, or audit errors → **ships anyway** (fail-open;
  an audit outage must never stall production).
- Kill switch: `insert into settings(key,value) values('claude_final_audit','{"on":false}')`.

Expected spend per published item drops from ~4-6 paid calls to **exactly one (~$0.01)**.

## Catalog reordered
`providers_catalog.json` `_default_tier`:
- standard: gemini-2.5-pro → gemini-2.5-flash → llama-3.3-70b-groq → deepseek → gpt-4o-mini → **claude-sonnet-4-5 last**
- cheap: gemini-2.5-flash first
`council._FREE_ORDER`: **gemini first**, then groq, then openrouter.

## Files (7)
```
pipeline/agent/brain.py                       writer: council-only, no silent paid fallback
pipeline/agent/grader.py                      free-first grading + force_claude audit path
pipeline/agentcore/council.py                 gemini first in free rotation
pipeline/agentcore/providers_catalog.json     Claude demoted to last resort
pipeline/workers/departments/cqo.py           _claude_final_audit + veto parking
pipeline/workers/runner.py                    VERSION 5.8.6
pipeline/tests/test_v582_council.py           mock updated for direct council.debate call
```

## Verification
`59 passed` (pytest), all modules `py_compile` clean.

## Deploy order
1. Upload this zip to GitHub → Railway rebuilds.
2. **Add GEMINI_API_KEY to Railway Variables** (the single highest-value change).
3. Confirm boot log shows `5.8.6`.
4. Resume the worker (kill switch is still on from the no_output_guard trip).
5. Watch `ledger` — brain/grader rows should now read `free:gemini...`, with
   `grader.final_audit` as the only Anthropic line.

## Note on the account documents
All 100 accounts already have their 8 documents written directly to Supabase from the
console session ($0 API spend) and `brand_bible` is stamped `prepared_by=claude_console`,
so `portfolio.tick` and `brand_studio` will skip regeneration. Agents read these as
their brand context. No worker action needed.
