# Agent-X v5.9.4 — "$25 Cap + Centered Banner"
All files are COMPLETE REPLACEMENTS. Drag-upload to GitHub keeping folder paths.

## What changed
1. pipeline/workers/common.py — FOUNDER POLICY: hard $25/month cap per account,
   enforced inside ceo_decide (the single gate every paid action passes through).
   New helpers: account_monthly_cap / account_monthly_spend / account_monthly_ok.
2. pipeline/workers/runner.py — VERSION bumped to 5.9.4 (so the banner confirms the deploy).
3. web/components/VersionBanner.tsx — banner text is now CENTERED; dismiss pinned right.
4. web/app/api/version/route.ts — web version 5.9.4.

## Verified before packaging
- 80/80 pytest green
- npm run build clean (zero TS errors)

## After upload
Railway boot line + banner must both say 5.9.4 and turn GREEN ("web and worker agree").
