export type Step = { key: string; title: string; detail: string; href?: string };
export type Track = {
  id: string; name: string; state: "live" | "soon";
  price: number; blurb: string; steps: Step[];
  incomeLayer: string;
};

export const TRACKS: Track[] = [
  {
    id: "instagram", name: "Instagram Reels · affiliate + bonuses", state: "live", price: 0,
    incomeLayer: "Affiliate first, Reels bonuses at eligibility",
    blurb: "Stand up a faceless niche page, ship daily Reels with the Studio, wire affiliate links and a comment→DM funnel from day one.",
    steps: [
      { key: "ig-1", title: "Create the account (Creator, not Business)", detail: "Fresh email, 2FA, Creator profile, niche handle. You own it — we never hold your login.", href: "https://www.instagram.com" },
      { key: "ig-2", title: "Lock your one-sentence angle", detail: "[Specific audience] + [daily promise]. Example: 'busy pros → one AI tool a day that saves an hour'. Every caption and CTA comes from this sentence." },
      { key: "ig-3", title: "Generate your first 3 Reels in the Studio", detail: "Agent produces script, voice, captioned 1080×1920 video. You watch and approve — you are always the editor." },
      { key: "ig-4", title: "Post manually for 7 days", detail: "No API required to start. Daily approved Reel, same posting window. The streak is the algorithm's trust signal." },
      { key: "ig-5", title: "Wire affiliate links + link-in-bio", detail: "Join 2-3 programs that match your niche (Amazon Associates, tool affiliate pages). Real links, real disclosure — money from view one." },
      { key: "ig-6", title: "Turn on comment→DM automation (ManyChat)", detail: "One keyword per video, DM delivers a free lead magnet, email capture → builds the list nobody can take from you.", href: "https://manychat.com" },
      { key: "ig-7", title: "Launch your $17-47 digital product", detail: "Sell to the list, not the feed: template pack, prompt bundle, Notion system. Gumroad / Lemon Squeezy handle payments globally.", href: "https://gumroad.com" },
      { key: "ig-8", title: "Apply for the Reels Bonus when eligible", detail: "Invite-only, country-dependent. We surface the metrics you need the day you qualify. Treat as bonus, never as plan A." },
    ],
  },
  {
    id: "youtube", name: "YouTube Shorts + long-form · YPP revenue", state: "live", price: 0,
    incomeLayer: "AdSense (YPP) — the only real 'paid per view' at scale",
    blurb: "Daily Shorts feed a weekly long-form video — the YouTube Partner Program is where views actually pay. Shorts alone pay pennies; the ladder pays dollars.",
    steps: [
      { key: "yt-1", title: "Create the channel (brand account)", detail: "Dedicated Gmail, 2FA, channel name matching your niche. Brand account so you can add managers later without sharing passwords.", href: "https://studio.youtube.com" },
      { key: "yt-2", title: "Post the same Shorts as Instagram (re-edited, not copied)", detail: "Native YouTube titles + end screens + chapters. Straight reposts get demonetized — original hooks survive.", href: "https://www.youtube.com" },
      { key: "yt-3", title: "Publish 1 long-form (6–10 min) per week", detail: "Listicles/tutorials in AI/business niches earn $2-15 RPM. Shorts are discovery; long-form is where watch hours and money live." },
      { key: "yt-4", title: "Hit the YPP threshold (1k subs + 4k watch hours OR 10M Shorts views / 90d)", detail: "Studio tracks progress. You apply from YouTube Studio the day you qualify." },
      { key: "yt-5", title: "Turn on AdSense + Super Thanks + affiliate links in description", detail: "Layered revenue: ads + fan funding + affiliate per video." },
    ],
  },
  {
    id: "tiktok", name: "TikTok · affiliate + Creator Rewards", state: "live", price: 0,
    incomeLayer: "Affiliate + TikTok Shop commissions; Rewards Program once eligible",
    blurb: "Same Studio output, native TikTok format (hooks in first 2 seconds, trending audio you pick). Affiliate links in bio + TikTok Shop commissions when you have access.",
    steps: [
      { key: "tt-1", title: "Create the TikTok account", detail: "Phone sign-up, Creator account, handle matching your other platforms. 2FA on day one.", href: "https://www.tiktok.com" },
      { key: "tt-2", title: "Native-post 7 days of Studio clips", detail: "Re-cut hooks for TikTok pacing. Use trending audio from the in-app library (agents can't pick that — you do)." },
      { key: "tt-3", title: "Join the TikTok Affiliate Program / TikTok Shop", detail: "Available in eligible countries once thresholds hit. Promote products you actually use and disclose." },
      { key: "tt-4", title: "Apply to the Creator Rewards Program at 10k followers + 100k views / 30d", detail: "Pays $0.40-1.20 / 1k qualified views for videos 60s+. Country-locked — we tell you the day your account qualifies." },
    ],
  },
  {
    id: "affiliate", name: "Affiliate marketing stack", state: "live", price: 0,
    incomeLayer: "Commissions from tools/products you feature",
    blurb: "The day-one money layer. Choose programs that match your niche, cloak links correctly, disclose everywhere, and let your content do the selling.",
    steps: [
      { key: "af-1", title: "Pick 3-5 programs your audience actually needs", detail: "Amazon Associates + 2-4 SaaS tools with recurring commissions. Never recommend something you haven't used." },
      { key: "af-2", title: "Build a clean link-in-bio page (Beacons / Stan / own page)", detail: "Group links by topic so viewers find what they asked for. Put your disclosure line at the TOP, not buried.", href: "https://beacons.ai" },
      { key: "af-3", title: "Build a resource page on your own domain", detail: "Future-proofs you against link-in-bio shutdowns. This page also ranks on Google over time." },
      { key: "af-4", title: "Track which video produces which click", detail: "UTM tags per video so you double down on the topics that convert, not the topics that just get views." },
    ],
  },
  {
    id: "store", name: "Ecommerce · rebrand & sell your own product", state: "live", price: 0,
    incomeLayer: "Direct product margin (3-5x markup)",
    blurb: "From product research to first sale: find a proven product, rebrand it, build a simple store, launch on creatives your Studio can produce, and kill losers fast.",
    steps: [
      { key: "st-1", title: "Reality check + starting budget", detail: "Minimum ~$300 to test (samples + first ad spend). Organic-only path exists if budget is tight — slower, but zero ad risk." },
      { key: "st-2", title: "Research 3 candidate products (Meta Ad Library + TikTok #tiktokmademebuyit)", detail: "Score each product 0-7 on the winner checklist. Only 6+/7 goes to sample.", href: "https://www.facebook.com/ads/library/" },
      { key: "st-3", title: "Order the top sample, build the brand name/domain/logo", detail: "Brand = 2-3 syllable name, .com or .co available, Canva wordmark, one niche not a general store." },
      { key: "st-4", title: "Build the store (Shopify)", detail: "Legal pages, one-country shipping to start, 3-5 product photos you shoot yourself. Demo products = no trust = no sale.", href: "https://www.shopify.com" },
      { key: "st-5", title: "Generate launch creatives in the Studio + run a $5/day test", detail: "3-5 angle videos per product. Kill anything with CPA above your breakeven by day 4; double down on winners." },
      { key: "st-6", title: "Rebrand packaging once at 20+ orders/week", detail: "Supplier adds your logo, custom insert card with QR to your social. That's when a commodity becomes a brand." },
    ],
  },
  {
    id: "digital", name: "Digital products · highest-margin income", state: "soon", price: 0,
    incomeLayer: "100%-margin downloads sold to your list",
    blurb: "Once you have an audience, a $17-47 digital product pays more per 1,000 followers than any ad or affiliate deal. Coming next module.",
    steps: [
      { key: "dp-1", title: "Identify the #1 question your audience asks", detail: "Mine comments and DMs. The product sells if it solves that ONE question end-to-end." },
      { key: "dp-2", title: "Build v1 in a weekend (Notion / PDF / video pack)", detail: "Outcome-named, not vague: 'The 50-prompt AI workday system' beats 'AI Guide'." },
      { key: "dp-3", title: "Sell via Gumroad / Lemon Squeezy", detail: "Handles VAT and global payouts from Turkey/UAE without you needing Stripe in every country.", href: "https://www.lemonsqueezy.com" },
      { key: "dp-4", title: "Sell to the list, not the feed", detail: "3-email sequence: free value → case study → offer. Never cold-DM your followers with a buy link." },
    ],
  },
];

export const trackById = (id: string) => TRACKS.find((t) => t.id === id);
