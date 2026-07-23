# AGENT-X — UNIT ECONOMICS & PRICING MODEL
**Date:** 2026-07-24 · REQ-UNITECON-1 · Companion to `docs/ROADMAP.md`
**Question answered:** can Agent-X sell **$2/day** covering 4–5 platforms (images + reels + marketing
tools) and keep profit? And should the founder raise the production budget?

---

## 1 · THE ANSWER IN ONE LINE

**Yes at $2/day — but only on a stills-and-motion pipeline. On true AI-video generation you lose
money on every single customer, every single day.** That one architectural choice swings COGS by
roughly 30×, and it is the whole pricing decision.

---

## 2 · WHAT A REEL ACTUALLY COSTS (component by component)

| Component | Cheap path | Cost | Premium path | Cost |
|---|---|---|---|---|
| Script (write + 1 rewrite) | free council (Gemini/Groq/OpenRouter) | **$0.000** | paid escalation | $0.002–0.02 |
| Grading / QA | free council | **$0.000** | paid verify pass | $0.01 |
| Art direction (v5.10.0) | 1 free call per reel | **$0.000** | paid | $0.01 |
| Captions + repurpose (4–5 platforms) | 1 combined free call | **$0.000** | paid | $0.003 |
| Images (6 frames) | FLUX-schnell class ≈$0.003/img | **$0.018** | FLUX-pro class ≈$0.04/img | $0.24 |
| Voiceover (~30s) | edge-tts | **$0.000** | ElevenLabs | $0.05–0.10 |
| Assembly / render | local ffmpeg | **$0.000** | — | — |
| **REEL SUBTOTAL** | | **≈$0.02** | | **≈$0.30–0.40** |
| **AI VIDEO instead of stills** | — | — | 6 × 5s clips @ $0.25–1.00 | **$1.50–6.00** |

**Carousel** (5 static slides, no voice): ≈**$0.015** cheap / ≈$0.20 premium.

### Realistic daily package at $2 retail

| Tier | Contents | Daily COGS | Gross margin at $2/day |
|---|---|---|---|
| **Free-first (default)** | 1 reel + 1 carousel + captions for 5 platforms | **$0.035** | **98%** |
| **Mixed (realistic)** | as above, ~30% of LLM calls escalate to paid, ElevenLabs voice | **$0.12–0.18** | **91–94%** |
| **Premium stills** | FLUX-pro images + ElevenLabs everywhere | **$0.45–0.60** | **70–78%** |
| **True AI video** | 1 AI-generated 30s reel | **$1.50–6.00** | **−200% to +25%** ❌ |

Add infrastructure (Railway + Vercel + Supabase ≈ $20–40/month) and at 100 customers that is
**$0.007–0.013 per customer per day** — a rounding error against $2.

**Verdict: $2/day works comfortably, with room for a 2–3× cost overrun, as long as the default
tier is stills + motion.**

---

## 3 · WHY YOUR CURRENT SPEND LOOKS ALARMING (and isn't)

Today: **$1.15 spent, 0 posts published.** That reads like $1.15/post → infinite cost.

It isn't production cost — it is **waste from the outage**: ideation churn, re-planning the same
stalled items, and repeated failed writer attempts. Fixed across v5.9.5–v5.9.9 (demand governor,
in-flight age-out, replan idempotency, escalation ladder).

**Do not price off today's numbers.** `settings.cost_per_post` (shipped v5.9.7) now computes the real
figure every 5 minutes. **Get 10 posts out, read that number, then price.** Everything above is a
model; that field will be the measurement.

---

## 4 · SHOULD YOU RAISE THE BUDGET? — YES, SPECIFICALLY

Current per-account daily budgets are **$0.50** (puppy.parent) and **$0.75** (glowup.daily). A single
escalated post can legitimately need $0.10–0.30 in a bad free-tier hour. Those caps are tight enough
that escalation will decline on budget grounds while you are trying to prove the pipeline works.

**Recommended settings while proving the loop (next ~2 weeks):**

| Setting | Now | Recommended | Why |
|---|---|---|---|
| Per-account daily budget | $0.50 / $0.75 | **$1.50** | Room for escalation to actually fire |
| Global daily budget | $2.50 | **$5.00** | 2 active accounts + headroom |
| Per-account monthly cap | $25 | **keep $25** | Correct ceiling; do not touch |
| Wallet balance | $1.00 | **$20–30** | Stops the wallet being the blocker |

That is a **temporary proving budget, not a steady-state one.** Once `cost_per_post` shows real
numbers, drop the daily cap to roughly **3× measured cost per post** and leave it there.

**Do not raise the $25 monthly cap.** At $2/day retail, a customer generates ~$60/month; a $25 ceiling
already guarantees ≥58% margin even in a worst case. It is your safety net — keep it.

---

## 5 · MOST COST-EFFICIENT STACK FOR THE QUALITY YOU WANT

Ordered by value per dollar, given what the audit found:

1. **Free LLM ladder for all text** (script, grade, art direction, captions). Now protected by the
   floor merge (v5.9.6) so it cannot silently shrink again. **$0.**
2. **Cheap-tier images, more of them.** Six good FLUX-schnell frames with real art direction beat two
   expensive frames with weak prompts. The v5.10.0 Art Director is worth more than a model upgrade.
3. **edge-tts by default, ElevenLabs only for accounts that convert.** Voice is the second-largest
   cost and the least correlated with retention early on.
4. **Motion over generation.** Ken Burns, parallax, and cut rhythm on well-directed stills reads as
   "produced" at ~1% of AI-video cost. Most faceless-reel output is exactly this.
5. **AI video as a paid upsell, never in the base tier.** Price it as its own SKU at cost + margin
   (e.g. $3–5 per AI-video reel), or cap it at N per month on a higher plan.

---

## 6 · PRICING RECOMMENDATION

| Plan | Price | Contents | Est. COGS/day | Margin |
|---|---|---|---|---|
| **Starter** | $2/day (~$59/mo) | 1 reel + 1 carousel, 5 platforms, captions, hashtags, scheduling | $0.04–0.18 | **91–98%** |
| **Growth** | $4/day (~$119/mo) | 2 reels + 2 carousels, premium voice, priority SLA | $0.30–0.50 | **88–93%** |
| **Studio** | $8/day (~$239/mo) | Growth + 4 AI-video reels/month + brand refresh | $1.20–2.00 | **75–85%** |

**Sequencing advice:** do not sell any plan until one account has published for 7 consecutive days.
The whole model above rests on a pipeline that has produced zero posts to date; selling before that
converts an engineering risk into a refund liability.

---

## 7 · ARE WE ON THE SAME PATH AS THE GENERATION PLATFORMS?

Partially — and the difference matters commercially.

| | Generation platforms (OpenArt-style) | Agent-X |
|---|---|---|
| Core unit | A human clicks, one asset appears | An account produces daily without a human |
| Sold as | Credits for creation | Operated outcome |
| Competes on | Model quality, speed, UI | Autonomy, cost governance, SLA, multi-account scale |
| Moat | Model access + brand | Orchestration nobody has bothered to build |

**Do not race them on generation.** They are better funded and generation quality is commoditising
monthly — every model improvement they buy, you also get, through the same APIs. Your defensible
position is the layer above: planning, budget intelligence, deadline enforcement, and running a
hundred brands unattended. Use their category's tools (FAL, BFL, GOAPI) as interchangeable suppliers
and keep the orchestration as the product.

**Practical implication:** the Art Director (v5.10.0) is the right amount of investment in generation
quality — it makes cheap models produce good frames. Building a video model, or a canvas editor, is not.
