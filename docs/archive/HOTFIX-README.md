# Agent-X v5.7.1 — HOTFIX (first production run findings)
Complete replacements. Push these 5 files; only Railway redeploys (no web changes).

Fixes, found live during tonight's first run:
1. GRADER MONEY LEAK: when daily budget ran out, the grader silently returned
   fake 6.0 scores -> "failed" -> triggered PAID rewrites in a loop. Now it
   reports skipped=True and the draft parks as UNGRADED in Studio ($0 spent) —
   you are the final gate anyway.
2. OFF-NICHE TOPICS: legacy strategy leaked generic AI topics ("3 free AI
   tools...") into your skincare/pet accounts. AI-topic filter now applies to
   ALL topic sources, not just trends.
3. glowup.daily had no skincare evergreen topics — added 5.
Tests: 45/45 green.
