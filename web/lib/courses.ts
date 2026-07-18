// Auto-structured course content. Each step gates the next behind a verification proof.
export type Verify = { type: "link" | "screenshot" | "text"; prompt: string };
export type CourseStep = { key: string; title: string; minutes: number; lesson: string[]; verify: Verify; resources?: { title: string; body: string }[] };
export type Module = { id: string; title: string; goal: string; steps: CourseStep[] };
export type Course = { id: string; name: string; modules: Module[] };
export const COURSES: Record<string, Course> = {
 "instagram": {
  "id": "instagram",
  "name": "AI Content Page \u2014 A to Z",
  "modules": [
   {
    "id": "m0",
    "title": "Module 0 \u2014 Foundations (read before touching anything)",
    "goal": "Understand the business you are building so every later step makes sense.",
    "steps": [
     {
      "key": "ig-m0-1",
      "title": "How this business actually makes money",
      "minutes": 10,
      "lesson": [
       "The page earns in layers, in this order: (1) affiliate commissions on tools you feature, (2) your own digital product once you have an audience, (3) services or a SaaS later. Views alone pay nothing.",
       "The asset you are building is TRUST in a niche, not follower count. 5,000 followers who click links beat 100,000 who scroll past.",
       "Timeline honesty: expect 30-60 days of daily posting before meaningful traction. Anyone promising faster is selling you something.",
       "Legal line you will follow forever: when a link earns you a commission, you disclose it (a simple 'links may earn us a commission' in bio + 'aff' note where relevant). You never claim or imply specific income results."
      ],
      "verify": {
       "type": "text",
       "prompt": "Type the one-layer answer: what is the FIRST money layer for your page, and what is the disclosure line you will use in your bio?"
      }
     },
     {
      "key": "ig-m0-2",
      "title": "Pick your niche angle and lock it",
      "minutes": 15,
      "lesson": [
       "Formula: [specific audience] + [daily promise]. Example: 'busy professionals -> one AI tool or trick a day that saves an hour'.",
       "Test your angle against three filters: Can you name 30 video topics right now? Are there affiliate-payable tools in it? Do big pages already exist (competition = demand)?",
       "Write it as one sentence. This sentence becomes your bio, your CTA, and the brief every AI agent in the Studio works from.",
       "Do NOT pick: general motivation, news commentary, anything requiring your face if you want faceless, or a niche with no products to link."
      ],
      "verify": {
       "type": "text",
       "prompt": "Paste your one-sentence angle: audience + daily promise."
      },
      "resources": [
       {
        "title": "Starter pack \u2014 AI for busy professionals",
        "body": "Angle sentence: Busy professionals -> one AI tool or trick a day that saves an hour.\n\nFirst 12 topics:\n1. The email tool that writes your replies in your voice\n2. Turn any meeting recording into action items in 2 minutes\n3. The free scheduler that ends back-and-forth emails\n4. Make ChatGPT remember how you like documents formatted\n5. One prompt that turns rambling notes into a clean brief\n6. The browser AI that summarizes any article before you commit\n7. Auto-sort your inbox with rules AI writes for you\n8. Turn a voice memo into a formatted report\n9. The Notion setup that runs itself\n10. Slides from a bullet list in 90 seconds\n11. The AI that preps you for any meeting from the invite alone\n12. Stop typing meeting minutes forever"
       },
       {
        "title": "Starter pack \u2014 AI for students",
        "body": "Angle sentence: Students -> study faster with AI without getting caught cheating yourself.\n\nFirst 12 topics:\n1. Turn any PDF into a personal tutor that quizzes you\n2. The flashcard method AI builds in minutes\n3. Summarize a 2-hour lecture recording before dinner\n4. The citation tool that never invents sources\n5. Make AI explain like you are 12, then like a professor\n6. Practice-exam generator from your own notes\n7. The free tool that checks your logic, not just grammar\n8. Plan a semester in 15 minutes\n9. Language-learning drills AI personalizes daily\n10. Turn a textbook chapter into a podcast for your commute\n11. The note system that connects ideas for you\n12. Beat procrastination with an AI accountability check-in"
       },
       {
        "title": "Starter pack \u2014 AI side-hustle tools",
        "body": "Angle sentence: Beginners -> free AI tools that do paid-tool jobs, one per day.\n\nFirst 12 topics:\n1. This free tool replaces a $30/mo subscription\n2. Design a logo in 10 minutes, zero skills\n3. The AI voice that sounds human enough to narrate\n4. Remove any background without Photoshop\n5. Write product descriptions that actually sell\n6. Free video subtitles in 90+ languages\n7. Turn one blog post into a week of social content\n8. The invoice generator freelancers actually use\n9. Research any market in 20 minutes\n10. AI headshots vs a $200 photographer\n11. Build a simple website by describing it\n12. The free scheduler that posts while you sleep"
       },
       {
        "title": "Starter pack \u2014 AI for parents",
        "body": "Angle sentence: Parents -> practical AI that buys back family time, one tip a day.\n\nFirst 12 topics:\n1. Meal-plan the whole week in 5 minutes\n2. The homework helper that teaches instead of answering\n3. Turn bedtime into custom stories starring your kid\n4. Family calendar chaos, solved by one assistant\n5. The screen-time tool that actually works\n6. Plan a birthday party with one prompt\n7. AI-checked chore charts kids follow\n8. Translate school letters instantly\n9. The budget tracker that talks like a human\n10. Photo books that make themselves\n11. Trip planning without 40 open tabs\n12. The reminder system that runs your household"
       },
       {
        "title": "Starter pack \u2014 AI in real estate",
        "body": "Angle sentence: Agents and investors -> AI moves that win listings and save hours.\n\nFirst 12 topics:\n1. Listing descriptions that sell in one prompt\n2. Virtual staging for the price of coffee\n3. The follow-up sequence that never forgets a lead\n4. Analyze a deal in 10 minutes with AI\n5. Neighborhood reports buyers actually read\n6. Turn a walkthrough video into a listing package\n7. The CRM prompt pack top agents use\n8. Price a property with AI-assisted comps\n9. Open-house sign-ins that follow up themselves\n10. Contract summaries in plain English\n11. Social content from one listing photo\n12. Cold outreach that does not sound cold"
       }
      ]
     }
    ]
   },
   {
    "id": "m1",
    "title": "Module 1 \u2014 Account setup, the correct way",
    "goal": "A clean Creator account that will never get flagged, that you fully own.",
    "steps": [
     {
      "key": "ig-m1-1",
      "title": "Fresh email + password hygiene",
      "minutes": 10,
      "lesson": [
       "Create a NEW email dedicated to this business (Gmail is fine). Never reuse a personal login. This email will own Instagram, your link-in-bio, and every affiliate account \u2014 one place, backed up.",
       "Password manager (Bitwarden free tier is enough) + save recovery codes the moment any service offers them.",
       "Why this matters: mixed personal/business accounts are the #1 cause of lockouts you cannot recover from."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of the new email inbox (address visible, contents can be blank)."
      }
     },
     {
      "key": "ig-m1-2",
      "title": "Create the Instagram account + convert to Creator",
      "minutes": 15,
      "lesson": [
       "Sign up on the PHONE app (not desktop) with the new email. Phone-created accounts trip fewer spam filters.",
       "Handle rules: readable, niche-hinting, no 'hustle/cash/money' words (they suppress reach and repel affiliates). Pattern that works: [niche].[format].[cadence] \u2014 e.g. ai.moves.daily.",
       "Immediately: Settings -> Account type -> switch to Creator (not Business \u2014 Creator gets the same tools with better reach treatment for individuals). Category: Education.",
       "Turn on two-factor authentication with an authenticator app, NOT SMS. Save the backup codes to your password manager."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of your profile showing the handle and the Creator badge in settings."
      }
     },
     {
      "key": "ig-m1-3",
      "title": "Profile that converts: photo, bio, highlights",
      "minutes": 20,
      "lesson": [
       "Profile photo: simple bold icon or wordmark on a solid color, readable at thumbnail size. Generate it in Canva in 10 minutes \u2014 no perfectionism.",
       "Bio formula, 3 lines: Line 1 = your angle sentence. Line 2 = proof or promise ('New drop every day at 6pm'). Line 3 = pointer to the link ('Free tool list below').",
       "Add the affiliate disclosure to the bio or the link page: 'Some links earn us a commission.'",
       "Skip highlights for now \u2014 empty highlights look worse than none. You will add them in week 2 from real posts."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of the finished profile (photo + 3-line bio visible)."
      }
     },
     {
      "key": "ig-m1-4",
      "title": "Warm-up protocol (do NOT skip)",
      "minutes": 10,
      "lesson": [
       "New accounts that immediately mass-post get shadow-throttled. For the first 48 hours: follow 10-15 accounts in your niche, watch 20+ Reels in the niche, like and leave 3-5 real comments a day. No posting yet.",
       "This teaches the algorithm what your account is about BEFORE your first post, so your first Reel gets shown to the right test audience.",
       "Meanwhile, your content is already being generated in the Studio (next module) \u2014 nothing is wasted."
      ],
      "verify": {
       "type": "text",
       "prompt": "List 5 niche accounts you followed and one comment you left (paste the comment text)."
      }
     }
    ]
   },
   {
    "id": "m2",
    "title": "Module 2 \u2014 Money rails before content",
    "goal": "Every view from post #1 can earn. No follower minimums.",
    "steps": [
     {
      "key": "ig-m2-1",
      "title": "Join 3 affiliate programs",
      "minutes": 30,
      "lesson": [
       "Start with tools you will genuinely feature. Solid first three for AI-education niches: ElevenLabs (voice), Notion (productivity), Canva (design) \u2014 all have free affiliate programs with no traffic minimums. Apply with your page handle + angle sentence as the description.",
       "Also acceptable: Amazon Associates for gadgets (low % but instant approval in most countries), or any tool in your niche with a 'Partners/Affiliates' footer link.",
       "Approval can take 1-5 days \u2014 this is why money rails come before content. Save every affiliate link in a note titled LINKS.",
       "Rule: never feature a tool ONLY because it pays. Audiences smell it and trust dies. Feature the best tool; link it if it pays."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of at least one affiliate dashboard showing your approved account (hide earnings/personal data)."
      }
     },
     {
      "key": "ig-m2-2",
      "title": "Build the link-in-bio page",
      "minutes": 20,
      "lesson": [
       "Use Linktree free, Beacons free, or a simple Notion page. Order: (1) the free value item ('My top 10 free AI tools' list), (2) 3-4 affiliate tool links with one-line benefits, (3) disclosure line at the bottom.",
       "Name links by BENEFIT not brand: 'The voice tool I use in every video' beats 'ElevenLabs'.",
       "Put the link in your Instagram bio. Test it on your phone in an incognito tab."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste your live link-in-bio URL."
      }
     }
    ]
   },
   {
    "id": "m3",
    "title": "Module 3 \u2014 Your content engine (the Studio)",
    "goal": "Generate, review, and own a production pipeline instead of editing videos by hand.",
    "steps": [
     {
      "key": "ig-m3-1",
      "title": "Tour the Studio + generate video #1",
      "minutes": 25,
      "lesson": [
       "Open the Studio. The board is your production line: idea -> drafted -> approved -> scheduled -> published. Nothing publishes without passing through you.",
       "Hit generate (or ask us to queue your first topics from your angle sentence). Each draft arrives with: a rendered 1080x1920 video preview, 3 hook options, a caption with hashtags, plus a ready tweet and LinkedIn post.",
       "Watch the video FULL SCREEN ON YOUR PHONE before judging \u2014 thumbnails lie about pacing."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of the Studio board showing at least one drafted item with its video preview."
      }
     },
     {
      "key": "ig-m3-2",
      "title": "Learn the two taste controls (this trains your AI)",
      "minutes": 15,
      "lesson": [
       "Control 1 \u2014 Pick the hook: every draft shows 3 hooks. Tap the strongest. Your picks are fed back to the writer as style examples, so hooks get closer to your taste every week.",
       "Control 2 \u2014 Reject with a reason: when a draft is weak, reject and tap why (weak hook / boring visuals / off topic...). The reason becomes a standing instruction the writer must obey on all future scripts.",
       "The quality bar to enforce: would YOU stop scrolling for this in the first second? If not, reject. A rejected draft costs cents; a mediocre published post costs reach."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot showing one hook you picked (green dot) OR one rejection reason you submitted."
      }
     },
     {
      "key": "ig-m3-3",
      "title": "Approve your first 3 videos",
      "minutes": 15,
      "lesson": [
       "Approve only drafts that pass: hook stops the scroll, every beat is one concrete idea, CTA matches your angle.",
       "Three approved videos = your first three days of posting, done in advance. This buffer is what makes the daily streak survivable."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of the board with 3 items in the approved (green) column."
      }
     }
    ]
   },
   {
    "id": "m4",
    "title": "Module 4 \u2014 Publish week one (manually, on purpose)",
    "goal": "Seven posts in seven days, posted by hand while automation approval runs in parallel.",
    "steps": [
     {
      "key": "ig-m4-1",
      "title": "Post #1, today",
      "minutes": 20,
      "lesson": [
       "Download the approved video from the Studio. In the Instagram app: create Reel -> upload -> tap 'Copy caption' in the Studio and paste -> post.",
       "Posting time: pick ONE time you can hit daily (6-8pm your audience's timezone is a safe default) and never change it mid-week. Consistency > optimization at this stage.",
       "First hour = golden hour: reply to every comment within 60 minutes (the Studio drafts replies for you once comments exist \u2014 until then, reply by hand, warmly, no links).",
       "Do not delete a 'flopped' post. Deletions hurt account signals; low views on early posts are normal calibration."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste the URL of your first published Reel."
      }
     },
     {
      "key": "ig-m4-2",
      "title": "Start the automation clock (Meta App Review)",
      "minutes": 30,
      "lesson": [
       "While you post manually, apply for API access so weeks 3+ can auto-publish. At developers.facebook.com: create an app -> add Instagram Graph API -> request instagram_content_publish + pages_read_engagement.",
       "In the review form, describe exactly what the tool does: 'Publishes my own pre-approved videos to my own account on a schedule.' Honest, minimal scopes = faster approval. Typical wait: 2-4 weeks \u2014 which is why this starts NOW, not when you need it.",
       "Nothing about your daily posting depends on this; it runs in the background."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of the app review submission confirmation (or the app dashboard showing 'In review')."
      }
     },
     {
      "key": "ig-m4-3",
      "title": "Days 2-7: the streak",
      "minutes": 60,
      "lesson": [
       "Daily rhythm (20 min): morning \u2014 approve tomorrow's draft in the Studio (pick hook, or reject with reason); evening \u2014 post today's video + paste caption; reply to all comments in hour one.",
       "Use the 'Copy tweet / Copy LinkedIn' buttons to cross-post 2 of your 7 videos this week \u2014 free distribution, same content.",
       "Rule of the week: NO strategy changes, no new formats, no panic. Seven data points first."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste links to Reels #3 and #7 (proves the streak held)."
      }
     }
    ]
   },
   {
    "id": "m5",
    "title": "Module 5 \u2014 Read the data, tighten the loop",
    "goal": "Turn week one's numbers into week two's plan using the Studio's weekly digest.",
    "steps": [
     {
      "key": "ig-m5-1",
      "title": "Your first weekly digest",
      "minutes": 20,
      "lesson": [
       "After 7 posts, open the Studio: the weekly digest card shows clips published, views, your best clip, spend, and \u2014 most important \u2014 average views per strategy bucket (proven / trend / experiment).",
       "Read Instagram's own numbers too: Insights -> per Reel -> watch time and saves. A Reel with high saves and low likes is a WINNER (saves predict follows).",
       "Decision rule for week 2: double the format of your best clip, kill the format of your worst, keep everything else identical. One variable at a time."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of the weekly digest card in your Studio."
      }
     },
     {
      "key": "ig-m5-2",
      "title": "Activate the money",
      "minutes": 15,
      "lesson": [
       "Once any Reel passes ~1,000 views: pin a comment on your best performer: 'Tool list is in the bio' (no hard sell in captions yet).",
       "Check your affiliate dashboards for CLICKS (not earnings \u2014 clicks are the leading indicator). If a featured tool gets clicks, feature it again in a different format within 5 days.",
       "Never post earnings screenshots publicly. It attracts the wrong audience and creates legal exposure. Your public proof page shows views, not income."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of an affiliate dashboard showing clicks > 0 (hide any personal data)."
      }
     }
    ]
   },
   {
    "id": "m6",
    "title": "Module 6 \u2014 Automate (after approval lands)",
    "goal": "Hand daily publishing to the worker; you keep only the taste decisions.",
    "steps": [
     {
      "key": "ig-m6-1",
      "title": "Connect your tokens",
      "minutes": 25,
      "lesson": [
       "When Meta approves: generate a long-lived access token, add IG_USER_ID + IG_ACCESS_TOKEN to the worker's environment, restart it once.",
       "From now on: approved -> scheduled -> published happens automatically, one per day at your set time. Your job shrinks to 10 min/day of approving and hook-picking.",
       "Safety rails already on: daily budget cap, kill switch in the Studio header (halts everything within one cycle), and idempotency (the same video can never double-post)."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste the link of the first Reel that the system published WITHOUT you touching the Instagram app."
      }
     },
     {
      "key": "ig-m6-2",
      "title": "Turn on comment replies",
      "minutes": 10,
      "lesson": [
       "In the Studio you have been seeing drafted replies under each published clip. Once tokens are live you can flip COMMUNITY_AUTOREPLY to let the system post them for you.",
       "Recommended: keep it on draft-mode for one more week and copy-paste the drafts. Watch its tone; when 9/10 drafts are ones you would send unchanged, flip it on."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of a comment thread where a system-drafted reply was used (posted by hand or auto)."
      }
     }
    ]
   },
   {
    "id": "m7",
    "title": "Module 7 \u2014 Scale decisions (day 30+)",
    "goal": "Know exactly what to do next based on which of three situations you are in.",
    "steps": [
     {
      "key": "ig-m7-1",
      "title": "The 30-day fork",
      "minutes": 20,
      "lesson": [
       "Situation A \u2014 a format is clearly winning (2-3x your average views): scale it. Increase to 2 posts/day of that family, launch the YouTube Shorts track (same engine, second surface).",
       "Situation B \u2014 flat but growing slowly: your hooks are the bottleneck 80% of the time. Spend one week rejecting every draft whose hook you would not personally tap. The taste loop will retrain the writer.",
       "Situation C \u2014 dead (avg <200 views after 30 daily posts): the ANGLE is wrong, not the system. Return to Module 0 step 2, pick a sharper audience, keep the same account (do not restart the warm-up penalty).",
       "Whichever situation: your digest history is the evidence. Decisions are made from the board, not from vibes."
      ],
      "verify": {
       "type": "text",
       "prompt": "Type which situation (A/B/C) you are in and the single change you are making, with the number that justifies it."
      }
     }
    ]
   }
  ]
 },
 "store": {
  "id": "store",
  "name": "Ecommerce \u2014 A to Z",
  "modules": [
   {
    "id": "e0",
    "title": "Module 0 \u2014 Reality check + budget",
    "goal": "Enter with correct expectations or do not enter at all.",
    "steps": [
     {
      "key": "ec-e0-1",
      "title": "The honest economics",
      "minutes": 15,
      "lesson": [
       "Ecommerce is a margin game: you buy at X, sell at 3-5X, and ads eat 30-50% of revenue while testing. Most first products fail \u2014 the skill is failing CHEAP and fast.",
       "Minimum realistic budget: product samples $30-80, store costs ~$40/first month, creative testing ads $150-300. Under ~$300 total, do the organic-only path (built into Module 6) and accept a slower ramp.",
       "The three ways people lose money: falling in love with one product, scaling before the numbers say so, and ignoring refunds/chargebacks. This course has a hard rule against each.",
       "Timeline: finding a working product typically takes 2-5 tested products. That is normal, not failure."
      ],
      "verify": {
       "type": "text",
       "prompt": "Type your total starting budget and which path that puts you on (paid-testing or organic-first)."
      }
     },
     {
      "key": "ec-e0-2",
      "title": "Pick your lane: niche store, not general store",
      "minutes": 10,
      "lesson": [
       "General stores (selling everything) are dead for beginners \u2014 no trust, no retargeting pool, weak creatives. One-product or one-NICHE stores win.",
       "Choose a niche you can judge products in: pets, fitness recovery, kitchen efficiency, desk setups, car accessories, beauty tools. You need to instinctively know if something is cool for that buyer.",
       "Write the buyer in one line: who they are + the feeling the product gives them. Example: 'cat owners who feel guilty leaving the cat home alone'."
      ],
      "verify": {
       "type": "text",
       "prompt": "Paste your niche + one-line buyer description."
      }
     }
    ]
   },
   {
    "id": "e1",
    "title": "Module 1 \u2014 Product research (tools + method)",
    "goal": "A shortlist of 3 candidate products backed by evidence, not gut feel.",
    "steps": [
     {
      "key": "ec-e1-1",
      "title": "Set up the free research stack",
      "minutes": 20,
      "lesson": [
       "Meta Ad Library (facebook.com/ads/library) \u2014 search your niche keywords, filter to active ads. This is the single best FREE tool: it shows what competitors are SPENDING on right now.",
       "TikTok search + hashtags (#tiktokmademebuyit + your niche) sorted by recent \u2014 what is organically moving this month.",
       "AliExpress + 'sort by orders' and Amazon Movers & Shakers \u2014 supply-side signal: what is actually shipping in volume.",
       "Google Trends \u2014 12-month view to catch seasonality and dying fads before you commit.",
       "Optional paid spy tools (Minea, PiPiAds) exist but are NOT needed for your first product. Evidence beats dashboards."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of Meta Ad Library showing active ads in your niche search."
      }
     },
     {
      "key": "ec-e1-2",
      "title": "The winning-product checklist",
      "minutes": 25,
      "lesson": [
       "Score every candidate 0-7, one point each: (1) solves a real problem or triggers a strong 'I want that' in 2 seconds, (2) not commonly found in local stores, (3) sells for 3x+ your landed cost, (4) target sell price $20-70 (impulse zone), (5) light + unbreakable to ship, (6) demonstrable in a 15-second video, (7) competitors' ads have been RUNNING 30+ days (proven spend).",
       "Only 6/7 or 7/7 products go to your shortlist. Be brutal \u2014 the checklist exists to overrule your excitement.",
       "Find each candidate's supply on AliExpress: at least 2 suppliers with 500+ orders and 4.6+ rating, ePacket/standard shipping under 12 days to your target market."
      ],
      "verify": {
       "type": "text",
       "prompt": "Paste your 3 shortlisted products with their checklist scores (e.g. 'LED pet fountain \u2014 6/7')."
      }
     },
     {
      "key": "ec-e1-3",
      "title": "Validate with evidence, then order samples",
      "minutes": 25,
      "lesson": [
       "For each shortlisted product, collect: 2+ competitors actively advertising it (Ad Library links), their engagement (comments asking 'where to buy' = demand; comments saying 'got mine broken' = your angle: quality), and price points across 3 stores.",
       "Order a sample of your top pick (top two if budget allows). You cannot make honest creatives, write real FAQs, or judge quality from supplier photos. Sample cost is tuition, not expense.",
       "While samples ship (7-14 days), you build the brand and store \u2014 the timeline stacks, nothing waits."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of your sample order confirmation (hide payment details)."
      }
     }
    ]
   },
   {
    "id": "e2",
    "title": "Module 2 \u2014 Brand creation + rebranding the product",
    "goal": "A brand shell that makes a commodity product feel like a company.",
    "steps": [
     {
      "key": "ec-e2-1",
      "title": "Name, availability, and the 15-minute identity",
      "minutes": 30,
      "lesson": [
       "Name rules: 2-3 syllables, easy to spell after hearing it once, hints the niche without boxing you into one product. Generate 20 options, kill 17.",
       "Availability check ALL of: .com or .co domain (Namecheap), Instagram + TikTok handle, and a quick trademark search (USPTO/TMview + your country's registry) for identical marks in your category. All four clear -> the name lives.",
       "Identity in Canva: pick 2 brand colors + 1 font, make a simple wordmark logo. Save as PNG with transparent background. Do not spend more than an hour \u2014 brands are built by consistency, not by logos."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste your registered domain OR the claimed Instagram handle URL for the brand."
      }
     },
     {
      "key": "ec-e2-2",
      "title": "Rebrand the product itself",
      "minutes": 25,
      "lesson": [
       "Level 1 (start here): rebrand the LISTING \u2014 your product photos (shoot the sample on your phone against clean backgrounds), your name for the product ('the CalmFount' not 'LED Automatic Pet Water Dispenser 2L'), your copy, your packaging insert (a thank-you card with QR to your page \u2014 order 100 printed cards cheaply or include digitally).",
       "Level 2 (after 20+ orders/week): ask your supplier for a custom logo on product/packaging (most do it at 100-300 unit MOQs) or move to a private agent (search 'dropshipping agent' \u2014 they hold your stock, brand it, ship in 5-8 days).",
       "The angle IS the rebrand: same product, different story. Competitors sell a water fountain; you sell 'never come home to a thirsty cat'. Write your angle in one sentence now."
      ],
      "verify": {
       "type": "text",
       "prompt": "Paste your product's new name + the one-sentence angle."
      },
      "resources": [
       {
        "title": "Template \u2014 supplier branding / MOQ request",
        "body": "Hi [name],\n\nI am selling [product] on my store and currently doing [X] orders/week. I want to move to branded packaging.\n\n1. What is your MOQ for adding my logo to the product / the box / an insert card?\n2. Unit price at 100 / 300 / 500 units with branding?\n3. Production + shipping time to [country]?\n4. Can you send a photo of a past branded example?\n\nLogo attached (vector). I am comparing 3 suppliers this week and will choose one long-term partner.\n\nThanks,\n[Your name], [Store name]"
       },
       {
        "title": "Template \u2014 private agent first contact",
        "body": "Hi, I run a store selling [product] with [X] orders/day and growing.\n\nLooking for an agent who can: source this product (link + photo attached), quality-check, ship to [main markets] in 5-10 days, and support branded packaging later.\n\nCould you quote: unit cost, shipping cost per order, and processing time? If pricing works I can route all orders to you this week.\n\n[Your name], [Store name]"
       }
      ]
     }
    ]
   },
   {
    "id": "e3",
    "title": "Module 3 \u2014 Build the store",
    "goal": "A store that looks trustworthy enough to take money from a stranger.",
    "steps": [
     {
      "key": "ec-e3-1",
      "title": "Platform + settings",
      "minutes": 30,
      "lesson": [
       "Shopify is the default (usually a $1 trial month, then ~$29-39/mo) \u2014 best app ecosystem, easiest checkout. Budget alternative: WooCommerce (free but you handle hosting/updates). Pick Shopify unless the budget truly forbids it.",
       "PAYMENTS \u2014 country-specific, check before building: Shopify Payments/Stripe require a registered business in many countries (in the UAE: a trade license or freelancer permit). Without one: PayPal where available, a merchant-of-record checkout, or launch while your license application runs. Verify current gateway terms for YOUR country \u2014 do not assume.",
       "Store settings pass: legal pages generated (refund, privacy, shipping, terms \u2014 Shopify has templates; EDIT the refund window and shipping times to what you can actually honor), currency, shipping zones (start: one country you understand), taxes on."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste your store URL (password page is fine at this stage)."
      },
      "resources": [
       {
        "title": "Payment gateways by situation (verify current terms before building)",
        "body": "UNITED STATES \u2014 sole proprietors can generally activate Shopify Payments/Stripe with SSN + bank account. Easiest starting point.\n\nEU/UK \u2014 Stripe and Shopify Payments widely available; most countries accept sole-trader registration (fast, cheap). Register first, then activate.\n\nUAE \u2014 Stripe and most gateways require a trade license or freelancer permit (mainland or free zone). Options in order: (1) get a freelancer permit (fastest license class), then Stripe/Telr/PayTabs; (2) until then, use a merchant-of-record checkout, which acts as the seller for you; (3) do NOT run payments through a personal PayPal at volume \u2014 accounts get frozen.\n\nEVERYWHERE \u2014 never fake your country or use someone else's details on a gateway. Frozen funds during a scaling month kills stores. The 30 minutes checking your country's exact requirements is the highest-ROI research in this course."
       }
      ]
     },
     {
      "key": "ec-e3-2",
      "title": "The product page that sells",
      "minutes": 45,
      "lesson": [
       "Anatomy, top to bottom: (1) gallery \u2014 5+ images: hero on white, lifestyle in use, size/scale, feature closeup, what's-in-the-box; (2) title = product name + core benefit; (3) price with anchor (compare-at showing a real, defensible discount); (4) 3 benefit bullets (outcomes, not specs); (5) shipping time stated plainly; (6) guarantee (30-day, and honor it); (7) FAQ answering the 5 objections you saw in competitor ad comments; (8) reviews section (empty is fine now \u2014 NEVER import fake reviews; first real orders fill it via a review app).",
       "Write copy from the buyer line and angle you already wrote. If you use AI to draft, edit until it sounds like a person who owns the product \u2014 because you do, the sample is on your desk.",
       "Speed check: run the page through PageSpeed Insights; compress images (tinypng). Slow pages burn ad money.",
       "Place a TEST order with a 100%-off code, then refund it \u2014 you must see your own checkout and confirmation email before a customer does."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of your completed product page (full scroll or key sections) + your test order confirmation email."
      }
     }
    ]
   },
   {
    "id": "e4",
    "title": "Module 4 \u2014 Creatives (your unfair advantage: the Studio)",
    "goal": "3 scroll-stopping video ads made from your sample + the content engine.",
    "steps": [
     {
      "key": "ec-e4-1",
      "title": "Shoot raw footage of your sample",
      "minutes": 30,
      "lesson": [
       "Phone camera, window light, 20-30 clips of 3-8 seconds: unboxing, the product working, closeups, the problem it solves (show the BEFORE), hands using it. Vertical, clean background, no talking needed.",
       "Steal shot ideas from the 3 best competitor ads you saved in Module 1 \u2014 shot TYPES are not copyrightable; their footage is. Never use competitor footage or supplier videos with other brands visible."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of your camera roll showing 15+ product clips."
      }
     },
     {
      "key": "ec-e4-2",
      "title": "Cut 3 ads with 3 different angles",
      "minutes": 40,
      "lesson": [
       "Three angles from one product: (1) problem-agitate-solve ('your cat hates stale water'), (2) wow/demo (the product doing the impressive thing in second one), (3) social-proof style ('why 10,000 cat owners switched').",
       "Structure per ad, 15-25s: hook frame (0-1s, the strongest visual or a bold text claim) -> 3-4 quick benefit shots -> price/offer card -> CTA. Captions on everything; most feeds are muted.",
       "Use the Studio to generate hooks and scripts for each angle (it writes hooks in three styles on demand), and CapCut (free) to cut the footage. Export 1080x1920.",
       "Also generate the ORGANIC content plan: the same engine that runs content pages runs your brand's page \u2014 one product tip/demo Reel daily builds free traffic and retargeting audiences while ads test."
      ],
      "verify": {
       "type": "link",
       "prompt": "Upload the 3 ads anywhere viewable (Drive/Dropbox) and paste the link."
      }
     }
    ]
   },
   {
    "id": "e5",
    "title": "Module 5 \u2014 Launch: organic first, then paid",
    "goal": "A launch sequence with hard kill rules that protect your budget.",
    "steps": [
     {
      "key": "ec-e5-1",
      "title": "Organic launch (everyone does this, paid or not)",
      "minutes": 30,
      "lesson": [
       "Brand accounts on TikTok + Instagram (use your Module 2 handles). Post 1-2 of your Reels/ads daily as organic content \u2014 TikTok especially can put a new product in front of 10k+ people for free.",
       "Bio links to the store. Reply to every comment. Watch which ANGLE gets organic traction \u2014 that angle gets the first ad dollars.",
       "Organic-only path (sub-$300 budgets): this is your whole engine for 2-4 weeks. Winning organic video (20k+ views or first organic sales) -> then put money behind it."
      ],
      "verify": {
       "type": "link",
       "prompt": "Paste links to your first 3 organic posts on the brand account."
      }
     },
     {
      "key": "ec-e5-2",
      "title": "Paid testing structure (if budget allows)",
      "minutes": 40,
      "lesson": [
       "Meta Ads Manager: 1 campaign (Sales objective) -> 3 ad sets at $10-15/day each, one per ANGLE, broad or 1-interest targeting (the algorithm finds buyers; your creative is the targeting) -> your ads inside.",
       "Warm-up reality: new ad accounts have spending limits and review delays of up to 24-48h. Submit ads, do not touch them for 3 days. Editing resets learning.",
       "KNOW YOUR NUMBERS before spending: breakeven ROAS = sell price / (sell price - product cost - shipping). Example: sell $39, landed cost $12 -> breakeven ROAS ~1.44. Write yours down.",
       "HARD KILL RULES (obey the sheet, not your hope): ad set spends 2x product sell price with ZERO sales -> kill it. CTR under 1% after $20 spend -> kill the creative. CPC over $2 in a $20-70 niche -> kill. One angle winning -> move budget there, do not 'give the others a chance'."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of Ads Manager showing the 1-campaign / 3-ad-set structure BEFORE significant spend (numbers can be blurred)."
      }
     },
     {
      "key": "ec-e5-3",
      "title": "The 72-hour verdict",
      "minutes": 20,
      "lesson": [
       "After 3 days of clean data, one of three verdicts: (1) profitable or near-breakeven with strong CTR -> Module 7 scaling; (2) clicks but no sales -> product page or offer problem, fix ONE thing (usually price anchor or shipping time clarity), run 2 more days; (3) no clicks anywhere -> creative or product problem -> next product from your shortlist. Total loss capped at your Module 0 testing budget.",
       "Log the verdict and numbers. Every killed product makes the next test smarter \u2014 this log is the actual asset."
      ],
      "verify": {
       "type": "text",
       "prompt": "Type your 72-hour numbers (spend, CTR, sales) and your verdict (1/2/3)."
      }
     }
    ]
   },
   {
    "id": "e6",
    "title": "Module 6 \u2014 Operations: orders, service, money protection",
    "goal": "Fulfill fast, keep customers calm, and do not get destroyed by chargebacks.",
    "steps": [
     {
      "key": "ec-e6-1",
      "title": "Fulfillment pipeline",
      "minutes": 25,
      "lesson": [
       "Connect DSers (free) to Shopify -> orders push to AliExpress in one click. Fulfill within 24h of every order, always.",
       "The moment you hit ~5 orders/day: message a private agent for quotes (faster shipping, branded packaging, better unit price). Until then, DSers is fine.",
       "Send tracking emails automatically (Shopify does this when you add tracking numbers). Customers with tracking do not open disputes."
      ],
      "verify": {
       "type": "screenshot",
       "prompt": "Screenshot of DSers connected to your store (or your first fulfilled order with tracking)."
      }
     },
     {
      "key": "ec-e6-2",
      "title": "Service + protection rules",
      "minutes": 20,
      "lesson": [
       "Reply to every customer email within 24h. Templates to prepare NOW: where-is-my-order (include tracking + honest timeline), damaged-item (photo -> instant replacement, no argument), refund-request (honor your policy without friction).",
       "Chargeback math: a dispute costs the refund + a fee + your gateway health. Refund fast and gracefully BEFORE it becomes a dispute \u2014 a refund is cheaper than a chargeback, always.",
       "Watch your dispute rate; above ~0.75% gateways start holding funds. Fast shipping + honest pages + fast refunds keep you at ~0."
      ],
      "verify": {
       "type": "text",
       "prompt": "Paste your where-is-my-order template (the one you will actually send)."
      },
      "resources": [
       {
        "title": "CS template \u2014 where is my order (WISMO)",
        "body": "Hi [name], thanks for reaching out!\n\nYour order shipped on [date] \u2014 tracking: [link]. Right now it shows [status], and delivery is expected by [date range].\n\nInternational tracking sometimes pauses a few days between scans even while moving. If it has not updated within [X] days, reply here and I will chase the carrier personally and make it right.\n\n[Your name]"
       },
       {
        "title": "CS template \u2014 damaged item",
        "body": "Hi [name], I am really sorry it arrived like that \u2014 not the experience we want.\n\nNo need to return anything. Send me a quick photo and I will ship a free replacement today, or refund you in full \u2014 your choice.\n\n[Your name]"
       },
       {
        "title": "CS template \u2014 refund request",
        "body": "Hi [name], of course \u2014 refund processed to your original payment method; it typically appears in 3-5 business days.\n\nIf you have 20 seconds: what was the main reason? It genuinely helps us improve.\n\nThanks for giving us a try.\n[Your name]"
       },
       {
        "title": "CS template \u2014 chargeback response evidence",
        "body": "When a dispute opens, submit within the deadline: (1) order confirmation with customer's own details, (2) tracking showing delivered status, (3) your refund policy page URL that was visible at checkout, (4) any email thread with the customer. Then tighten whatever caused it \u2014 most chargebacks are slow shipping or an unclear product page, not fraud."
       }
      ]
     }
    ]
   },
   {
    "id": "e7",
    "title": "Module 7 \u2014 Scale or kill",
    "goal": "A decision tree that turns one winning product into a real business.",
    "steps": [
     {
      "key": "ec-e7-1",
      "title": "Scaling a winner",
      "minutes": 30,
      "lesson": [
       "Vertical: raise winning ad set budgets +20-30% every 3 days (bigger jumps reset learning). Horizontal: duplicate winners into new ad sets with fresh creatives (make 2 new ads WEEKLY from your footage + Studio hooks \u2014 creative fatigue kills winners in 2-3 weeks).",
       "Retargeting: once past ~500 site visitors, a $5-10/day retargeting ad set (viewed product, no purchase) is usually your cheapest sales.",
       "Operations scale-up in the same week: private agent confirmed, branded packaging ordered, and email capture on the store (10% off first order) \u2014 the list becomes your free repeat-sales channel.",
       "Product #2: your winner defines the niche \u2014 add complementary products the SAME buyer wants. The store becomes a brand; repeat customers make the margins real."
      ],
      "verify": {
       "type": "text",
       "prompt": "Type your current daily budget, ROAS, and this week's scale action (or 'not there yet + what you are testing')."
      }
     }
    ]
   }
  ]
 }
};
export const courseById = (id: string) => COURSES[id];
export const courseSteps = (c: Course) => c.modules.flatMap((m) => m.steps);
