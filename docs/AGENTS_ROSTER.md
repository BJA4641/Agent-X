# Agent-X — Full Agent Roster (18 agents)

The system runs **18 specialized AI agents** that collaborate like a real agency to produce content for all 100+ social brands. Every agent respects pause/resume, persistent memory, brand docs, trend data, and the 8/10 quality gate.

## Pipeline Order (per post)

| # | Agent | Emoji | Responsibility | Inputs | Outputs | Cost |
|---|-------|-------|---------------|--------|---------|------|
| 1 | **Trend Scout** | 🔭 | Maintains library of viral hook/structure/audio patterns | Scrapes + curated bank | `trend_items` rows, `recent_trends()` block | $0 (curated, rotates) |
| 2 | **Researcher** | 🔎 | Compiles niche keywords, competitor angles, audience questions | Niche, brand angle | Memory entries with research brief | ~$0.02/account (once) |
| 3 | **Architect** | 🏛️ | Writes FULL business plan (13 docs per account: exec summary, vision, revenue, brand identity, visual identity, marketing strategy, IG/TikTok/YT playbooks, content calendar, content rules, hashtags/SEO, production SOP) | Niche, memory, trends, research | 13 markdown documents in `account_documents` | ~$0.08/account (once) |
| 4 | **Strategist** | 📋 | Plans 10 kickoff posts per account using brand docs + trends + founder notes; assigns pillar/trend pattern | Brand docs, trends, memory | 10 rows in `account_posts` (planned) | ~$0.06/account (once) |
| 5 | **Planner** | 📅 | Maintains the content calendar, feeds next-due posts to writer | Content calendar doc, post statuses | Feeds board items; scheduled_at timestamps | $0 |
| 6 | **Writer (Brain)** | ✍️ | Writes director-grade scripts with full shot list (voiceover, on-screen text, visual prompt, camera, transition, SFX, duration per beat); uses brand docs + memory + trends + grader feedback | Topic, brand docs, trends, memory, grade history | Full script JSON (hook, 6-7 beats, cta, captions) | ~$0.02/post + $0.02/rewrite |
| 7 | **Visuals** | 🎨 | Renders beat frames (Gemini AI image OR procedural gradient + overlays); applies color grade, bottom darkening, stickers/progress dots/hook banner/CTA card | Beat image prompt, style, hook word | Per-beat JPG frames (1080x1920) | $0 (procedural) or ~$0.03/image |
| 8 | **Voice** | 🎙️ | Generates narration (edge-tts free, or ElevenLabs for premium) | Narration text | MP3 audio file | $0 (edge-tts) or ~$0.08/post (ElevenLabs) |
| 9 | **Editor (Composer)** | 🎬 | Assembles final video: per-beat Ken Burns + transitions, burns word-by-word ASS captions (MrBeast-style, yellow power words), mixes voice + ducked music + per-cut SFX, loudnorm | Frames, audio, captions, SFX, music | Final 1080x1920 MP4 reel | $0 (ffmpeg) |
| 10 | **QA** | 🔍 | Checks hook, script length, claim safety, brand compliance | Script + brand content_rules | Pass/fail; flags issues to writer | $0 (rule-based) |
| 11 | **Grader** | 🎯 | Scores every draft on 6 axes (hook/visuals/pacing/audio/caption/CTA) 1-10; requires ≥8/10 average; provides concrete fix instruction; triggers up to 2 rewrites | Script, memory, trends, past feedback | `content_grades` row + pass/fail; memory entry with feedback | ~$0.015/grade × up to 3 attempts |
| 12 | **SEO** | 🔖 | Selects hashtag set (3 big + 4 mid + 3 niche), writes first-comment engagement bait, YouTube title, alt text | Script, hashtags_seo doc | Final hashtags, comment, alt text, YT title | $0 (rule-based) |
| 13 | **Publisher** | 📤 | Uploads preview to Supabase storage, schedules approved posts, cross-posts to connected social accounts | Final MP4, captions, hashtags | `video_url`, scheduled_at, publish receipts | $0 |
| 14 | **Analytics** | 📊 | Pulls metrics (views, likes, shares, comments) per published post | Published post | Metrics dict in board payload | ~$0 (API calls) |
| 15 | **Community** | 💬 | Drafts replies to comments; drafts first-comment pin | Metrics, post | Community reply drafts | $0 (simple) or ~$0.01/post (LLM) |
| 16 | **Digest** | 📬 | Daily summary: what ran, what failed, spend, grades, top performer | Ledger + events + grades | Daily digest event | ~$0 |
| 17 | **Budget (Ledger)** | 💰 | Tracks API spend per agent/model/post; enforces daily budget cap; rejects work if over budget | All LLM/image calls | run_ledger rows, spend remaining | $0 |
| 18 | **System/Ops** | ⚙️ | Boot, heartbeat, idle chatter, retries, kill switch, pause/resume enforcement | Config, signals | System events | $0 |

## Quality Gate (8/10 rule)
Every post goes through: Writer → QA → Grader. If grader < 8/10:
  1. Grader writes concrete fix instruction
  2. Writer rewrites using fix + previous feedback + memory
  3. Re-grade (max 2 rewrites)
  4. If still < 8/10: post is rejected, reason saved to memory (so future posts learn)

## Continuous Learning
Every post feeds back into the system:
  - Analytics results → Analyst stores winning patterns
  - Grader scores → memory (failed feedback + passed examples)
  - Founder chat (project + account level) → memory (always obeyed)
  - Memory is loaded by Architect (next rebrand), Strategist (next batch), Writer (every script), Grader (every grade)

## Adding a New Account (automatic flow)
1. Account created (status = needs_setup) → Architect writes 13 docs → status = strategizing
2. Researcher runs once per account → saves brief to memory
3. Strategist plans 10 posts → status = ready
4. Planner dequeues 1 post/tick → Writer scripts (with grader loop) → Visuals + Voice + Editor produce MP4
5. SEO adds hashtags/first-comment → status = drafted (awaiting approval)
6. User approves → Publisher schedules → Analytics pull metrics → Community replies

The orchestrator ticks every 60 seconds and only works on 1 non-paused account at a time (per the user's request).
