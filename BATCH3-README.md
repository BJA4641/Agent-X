# Agent-X v5.7.0 — BATCH 3
All files are COMPLETE REPLACEMENTS. Drag-upload preserving paths.

## What's inside
1. SOFT PAUSE (new "Pause intake" button in Studio next to Emergency stop):
   takes no NEW content work, lets in-flight renders finish. Worker respects it
   via settings key `soft_pause`. Kill switch renamed "Emergency stop" in UI.
2. 📚 ALL DOCUMENTS tab on every account page: read ALL 18 doc types
   (business plan, revenue model, playbooks, strategy...) + EDIT + Save.
   Edits are versioned (agent="human_edit", version bumps). Agents read your
   edited docs on the very next job.
3. Brand kit progress rows are now clickable (open the doc).
4. GET /api/version → {web, worker:{version, heartbeat_age_s, alive}}.
5. Worker VERSION → 5.7.0. Tests: 43/43 green. `npm run build`: clean.

## After pushing
Railway + Vercel auto-redeploy. Then in Studio press "Resume worker".
Active accounts: glowup.daily (produces immediately), puppy.parent
(Architect writes its full brand kit first, then produces).
