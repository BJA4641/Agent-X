/**
 * POST /api/admin/seed-demo
 * Admin only — creates 21 niche projects × 5 accounts each (105 total) for testing.
 * Accounts start as 'needs_setup' so the Architect picks them up on next tick.
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

// 21 niches × 5 accounts each (mirrors pipeline/agent/niches.py)
const NICHE_EMOJI: Record<string,string> = {
  ai_tools:"🤖",finance:"💰",make_money_online:"🤑",fitness:"💪",weight_loss:"⚖️",
  skincare:"✨",men_style:"👔",cooking:"🍳",home_hacks:"🏠",pets:"🐾",travel:"✈️",
  saas:"🚀",ecommerce:"🛒",coding:"💻",psychology:"🧠",productivity:"⚡",dating:"❤️",
  gaming:"🎮",real_estate:"🏠",luxury:"💎",motivation:"🔥",
};

const ACCOUNTS: Record<string, {name:string;handle:string;emoji:string;platforms:string[];angle:string;budget:number}[]> = {
  ai_tools: [
    {name:"AI Tool Daily",handle:"aitool.daily",emoji:"🤖",platforms:["instagram","tiktok","youtube_shorts"],angle:"one AI tool a day, hyper-specific",budget:1.0},
    {name:"Prompt Hacks",handle:"prompt.hacks",emoji:"✨",platforms:["instagram","tiktok"],angle:"copy-paste prompts that save hours",budget:0.75},
    {name:"Agent Lab",handle:"agentlab",emoji:"🧠",platforms:["tiktok","youtube_shorts","x"],angle:"autonomous AI agents",budget:0.75},
    {name:"Code Faster",handle:"codefaster",emoji:"💻",platforms:["youtube_shorts","x"],angle:"AI for devs",budget:0.5},
    {name:"AI Money Moves",handle:"ai.money",emoji:"💰",platforms:["instagram","tiktok"],angle:"AI side hustles",budget:1.0},
  ],
  finance: [
    {name:"Side Hustle Lab",handle:"sidehustle.lab",emoji:"💸",platforms:["instagram","tiktok","youtube_shorts"],angle:"one actionable side hustle per post",budget:1.0},
    {name:"Invest Simple",handle:"invest.simple",emoji:"📈",platforms:["youtube_shorts","instagram"],angle:"beginner investing",budget:0.5},
    {name:"Budget Bro",handle:"budget.bro",emoji:"💵",platforms:["tiktok","instagram"],angle:"save money hacks",budget:0.5},
    {name:"FIRE Diaries",handle:"fire.diaries",emoji:"🔥",platforms:["youtube_shorts","x"],angle:"early retirement",budget:0.5},
    {name:"Credit Fix",handle:"credit.fix",emoji:"💳",platforms:["instagram","tiktok"],angle:"credit score hacks",budget:0.5},
  ],
  make_money_online: [
    {name:"Print On Demand Pro",handle:"pod.pro",emoji:"👕",platforms:["tiktok","instagram","youtube_shorts"],angle:"print-on-demand case studies",budget:0.75},
    {name:"YouTube Growth Lab",handle:"yt.growth",emoji:"▶️",platforms:["youtube_shorts","tiktok"],angle:"algorithm faceless growth",budget:0.75},
    {name:"Affiliate Atlas",handle:"affiliate.atlas",emoji:"🔗",platforms:["tiktok","youtube_shorts"],angle:"affiliate case studies",budget:0.75},
    {name:"Digital Products 101",handle:"digital.products",emoji:"📲",platforms:["instagram","tiktok"],angle:"sell digital downloads",budget:0.5},
    {name:"Remote Job Finds",handle:"remote.funds",emoji:"🏠",platforms:["tiktok","linkedin"],angle:"high-paying remote jobs",budget:0.5},
  ],
  fitness: [
    {name:"Home Gains",handle:"home.gains",emoji:"🏋️",platforms:["instagram","tiktok","youtube_shorts"],angle:"no-equipment home workouts",budget:0.75},
    {name:"No Gym Fit",handle:"nogym.fit",emoji:"💪",platforms:["tiktok","instagram"],angle:"bodyweight-only",budget:0.5},
    {name:"Protein Kitchen",handle:"protein.kitchen",emoji:"🥗",platforms:["instagram","tiktok"],angle:"high-protein meals",budget:0.5},
    {name:"Couch to 5k",handle:"couch25k",emoji:"🏃",platforms:["youtube_shorts","instagram"],angle:"beginner running",budget:0.5},
    {name:"Mobility Fix",handle:"mobility.fix",emoji:"🧘",platforms:["instagram","tiktok"],angle:"5-min mobility routines",budget:0.5},
  ],
  weight_loss: [
    {name:"Calorie Hacks",handle:"calorie.hacks",emoji:"🥗",platforms:["tiktok","instagram"],angle:"low-calorie swaps",budget:0.75},
    {name:"Meal Prep Queen",handle:"mealprep.q",emoji:"🍱",platforms:["instagram","tiktok"],angle:"60-minute meal prep",budget:0.5},
    {name:"Fat Loss Facts",handle:"fatloss.facts",emoji:"🔥",platforms:["tiktok","youtube_shorts"],angle:"evidence-based fat loss",budget:0.5},
    {name:"Sugar Free Me",handle:"sugar.free",emoji:"🚫",platforms:["instagram","tiktok"],angle:"hidden sugar traps",budget:0.5},
    {name:"Intermittent Fast",handle:"fast.daily",emoji:"⏱️",platforms:["tiktok","youtube_shorts"],angle:"IF for beginners",budget:0.5},
  ],
  skincare: [
    {name:"Glow Up Daily",handle:"glowup.daily",emoji:"✨",platforms:["instagram","tiktok"],angle:"affordable routines",budget:0.75},
    {name:"Skin Science",handle:"skin.science",emoji:"🔬",platforms:["youtube_shorts","instagram"],angle:"evidence-based reviews",budget:0.5},
    {name:"Budget Glow",handle:"budget.glow",emoji:"💄",platforms:["tiktok","instagram"],angle:"drugstore dupes",budget:0.5},
    {name:"Acne Diaries",handle:"acne.diaries",emoji:"🧴",platforms:["tiktok","instagram"],angle:"honest journeys",budget:0.5},
    {name:"SPF Everything",handle:"spf.daily",emoji:"☀️",platforms:["instagram","tiktok"],angle:"sunscreen reviews",budget:0.5},
  ],
  men_style: [
    {name:"Capsule Wardrobe Guy",handle:"capsule.guy",emoji:"👕",platforms:["instagram","tiktok"],angle:"15 items = 100 outfits",budget:0.5},
    {name:"Budget Grooming",handle:"budget.groom",emoji:"🧔",platforms:["tiktok","youtube_shorts"],angle:"affordable grooming",budget:0.5},
    {name:"Date Fit Check",handle:"date.fit",emoji:"👔",platforms:["tiktok","instagram"],angle:"outfits for every occasion",budget:0.5},
    {name:"Fragrance Finds",handle:"scent.finds",emoji:"🌬️",platforms:["tiktok","youtube_shorts"],angle:"colognes by budget",budget:0.5},
    {name:"Sneaker Score",handle:"sneaker.score",emoji:"👟",platforms:["tiktok","instagram"],angle:"sneaker drops and deals",budget:0.5},
  ],
  cooking: [
    {name:"10 Min Meals",handle:"10min.meals",emoji:"⏱️",platforms:["instagram","tiktok","youtube_shorts"],angle:"10 minutes, 5 ingredients",budget:0.75},
    {name:"Student Kitchen",handle:"student.kitchen",emoji:"🍜",platforms:["tiktok","instagram"],angle:"dorm cooking",budget:0.5},
    {name:"Protein Plate",handle:"protein.plate",emoji:"🥩",platforms:["instagram","tiktok"],angle:"high-protein low-cal",budget:0.5},
    {name:"Budget Bites",handle:"budget.bites",emoji:"🥪",platforms:["tiktok","youtube_shorts"],angle:"under $3/serving",budget:0.5},
    {name:"Air Fryer Life",handle:"airfryer.life",emoji:"🍟",platforms:["instagram","tiktok"],angle:"air fryer everything",budget:0.5},
  ],
  home_hacks: [
    {name:"Dollar Tree Hacks",handle:"dollartree.hacks",emoji:"💵",platforms:["tiktok","instagram"],angle:"$1 organization finds",budget:0.5},
    {name:"Small Space Living",handle:"small.spaces",emoji:"🏙️",platforms:["instagram","tiktok"],angle:"apartment organization",budget:0.5},
    {name:"Clean With Me",handle:"clean.daily",emoji:"🧼",platforms:["tiktok","youtube_shorts"],angle:"speed cleaning",budget:0.5},
    {name:"Renter Friendly",handle:"renter.friendly",emoji:"🔨",platforms:["tiktok","instagram"],angle:"no-drill upgrades",budget:0.5},
    {name:"IKEA Hack Lab",handle:"ikea.hacks",emoji:"🪑",platforms:["instagram","tiktok"],angle:"IKEA upgrades",budget:0.5},
  ],
  pets: [
    {name:"Dog Training Tips",handle:"dog.training",emoji:"🐕",platforms:["tiktok","instagram","youtube_shorts"],angle:"30-second fixes",budget:0.5},
    {name:"Cat Facts Daily",handle:"cat.facts",emoji:"🐈",platforms:["tiktok","instagram"],angle:"cat behavior tips",budget:0.5},
    {name:"Puppy Parenting",handle:"puppy.parent",emoji:"🐶",platforms:["instagram","tiktok"],angle:"first-week puppy survival",budget:0.5},
    {name:"Pet Budget Finds",handle:"pet.finds",emoji:"🦴",platforms:["tiktok"],angle:"pet products under $20",budget:0.5},
    {name:"Rescue Stories",handle:"rescue.pets",emoji:"❤️",platforms:["tiktok","youtube_shorts"],angle:"rescue wins",budget:0.5},
  ],
  travel: [
    {name:"Flight Hacker",handle:"flight.hacker",emoji:"✈️",platforms:["tiktok","instagram"],angle:"mistake fares, points",budget:0.5},
    {name:"Carry On Only",handle:"carryon.only",emoji:"🎒",platforms:["instagram","tiktok"],angle:"pack week in carry-on",budget:0.5},
    {name:"Budget Country Guide",handle:"budget.country",emoji:"🌍",platforms:["youtube_shorts","tiktok"],angle:"$50/day country guides",budget:0.5},
    {name:"Hidden Gems",handle:"hidden.gems",emoji:"🗺️",platforms:["tiktok","instagram"],angle:"underrated spots",budget:0.5},
    {name:"Digital Nomad Daily",handle:"nomad.daily",emoji:"💻",platforms:["tiktok","x"],angle:"nomad city rankings",budget:0.5},
  ],
  saas: [
    {name:"Indie Hackers Daily",handle:"indie.daily",emoji:"🚀",platforms:["x","linkedin","youtube_shorts"],angle:"revenue numbers",budget:1.0},
    {name:"Micro SaaS Lab",handle:"microsaas.lab",emoji:"🔧",platforms:["x","youtube_shorts"],angle:"no-code SaaS",budget:0.75},
    {name:"Launch Log",handle:"launch.log",emoji:"📊",platforms:["x","linkedin"],angle:"launch teardowns",budget:0.5},
    {name:"Pricing Teardown",handle:"pricing.teardown",emoji:"💲",platforms:["linkedin","youtube_shorts"],angle:"pricing pages analysed",budget:0.5},
    {name:"Cold Outbound AI",handle:"outbound.ai",emoji:"✉️",platforms:["linkedin","x"],angle:"AI cold email",budget:0.5},
  ],
  ecommerce: [
    {name:"Winning Products",handle:"winning.products",emoji:"🏆",platforms:["tiktok","youtube_shorts"],angle:"viral products this week",budget:1.0},
    {name:"Shopify Starter",handle:"shopify.start",emoji:"🛍️",platforms:["youtube_shorts","tiktok"],angle:"store in a weekend",budget:0.75},
    {name:"Ad Library Spy",handle:"ad.spy",emoji:"👀",platforms:["tiktok","youtube_shorts"],angle:"profitable ads",budget:0.75},
    {name:"Printful Profits",handle:"printful.profits",emoji:"👕",platforms:["tiktok","instagram"],angle:"POD winners",budget:0.5},
    {name:"Amazon FBA Finds",handle:"fba.finds",emoji:"📦",platforms:["youtube_shorts"],angle:"FBA research breakdowns",budget:0.5},
  ],
  coding: [
    {name:"VS Code Tricks",handle:"vscode.tricks",emoji:"⌨️",platforms:["tiktok","youtube_shorts","x"],angle:"VS Code shortcuts",budget:0.5},
    {name:"Git in 60s",handle:"git.daily",emoji:"🔀",platforms:["x","youtube_shorts"],angle:"Git in 60 seconds",budget:0.5},
    {name:"Junior Dev Tips",handle:"junior.dev",emoji:"🐣",platforms:["tiktok","youtube_shorts"],angle:"what I wish I knew",budget:0.5},
    {name:"AI Code Review",handle:"ai.code",emoji:"🤖",platforms:["youtube_shorts","x"],angle:"AI coding tools",budget:0.5},
    {name:"Framework Fight",handle:"framework.fight",emoji:"🥊",platforms:["x","youtube_shorts"],angle:"React vs Vue vs Svelte",budget:0.5},
  ],
  psychology: [
    {name:"Dark Psychology Hub",handle:"dark.psych",emoji:"🎭",platforms:["tiktok","youtube_shorts"],angle:"manipulation to recognize",budget:0.75},
    {name:"Body Language 101",handle:"body.language",emoji:"👀",platforms:["tiktok","instagram"],angle:"read anyone instantly",budget:0.5},
    {name:"Cognitive Biases Daily",handle:"bias.daily",emoji:"🧩",platforms:["youtube_shorts","x"],angle:"one bias per day",budget:0.5},
    {name:"Persuasion Hacks",handle:"persuasion.hacks",emoji:"🗣️",platforms:["linkedin","tiktok"],angle:"get people to say yes",budget:0.5},
    {name:"Stoic Daily",handle:"stoic.daily",emoji:"📜",platforms:["instagram","tiktok"],angle:"stoic wisdom",budget:0.5},
  ],
  productivity: [
    {name:"Notion Hacks",handle:"notion.hacks",emoji:"📓",platforms:["tiktok","youtube_shorts"],angle:"one Notion trick",budget:0.5},
    {name:"Deep Work Daily",handle:"deep.work",emoji:"🎯",platforms:["youtube_shorts","x"],angle:"focus hacks",budget:0.5},
    {name:"Morning Routine Wins",handle:"am.routine",emoji:"🌅",platforms:["instagram","tiktok"],angle:"top performer routines",budget:0.5},
    {name:"Quit Bad Habits",handle:"quit.habits",emoji:"🚭",platforms:["tiktok","youtube_shorts"],angle:"dopamine reset",budget:0.5},
    {name:"One Book A Week",handle:"one.book",emoji:"📚",platforms:["tiktok","instagram"],angle:"one insight per post",budget:0.5},
  ],
  dating: [
    {name:"Text Game Tips",handle:"text.game",emoji:"📱",platforms:["tiktok","instagram"],angle:"texts that get replies",budget:0.5},
    {name:"Attraction Signs",handle:"attraction.signs",emoji:"👀",platforms:["tiktok"],angle:"signs they are into you",budget:0.5},
    {name:"Red Flags Daily",handle:"red.flags",emoji:"🚩",platforms:["tiktok","instagram"],angle:"dating red flags",budget:0.5},
    {name:"First Date Fix",handle:"first.date",emoji:"🍷",platforms:["tiktok"],angle:"first date mistakes",budget:0.5},
    {name:"Healthy Couple Tips",handle:"healthy.couple",emoji:"💞",platforms:["instagram","tiktok"],angle:"communication habits",budget:0.5},
  ],
  gaming: [
    {name:"Easter Egg Hunt",handle:"ee.hunt",emoji:"🥚",platforms:["tiktok","youtube_shorts"],angle:"hidden game details",budget:0.5},
    {name:"Pro Settings",handle:"pro.settings",emoji:"⚙️",platforms:["tiktok","youtube_shorts"],angle:"pro player settings",budget:0.5},
    {name:"Broken Game Clips",handle:"broken.game",emoji:"💥",platforms:["tiktok","youtube_shorts"],angle:"glitches & mechanics",budget:0.5},
    {name:"Indie Gem Finds",handle:"indie.gems",emoji:"💎",platforms:["tiktok","youtube_shorts"],angle:"underrated games",budget:0.5},
    {name:"Speedrun Highlights",handle:"speedrun.wins",emoji:"⏱️",platforms:["youtube_shorts","tiktok"],angle:"WR clips explained",budget:0.5},
  ],
  real_estate: [
    {name:"House Hack 101",handle:"house.hack",emoji:"🏘️",platforms:["tiktok","youtube_shorts"],angle:"live free via house hacking",budget:0.5},
    {name:"Airbnb Income Lab",handle:"airbnb.lab",emoji:"🛏️",platforms:["instagram","tiktok"],angle:"short-term rental wins",budget:0.5},
    {name:"Wholesaling Hub",handle:"whole.saling",emoji:"🤝",platforms:["youtube_shorts"],angle:"wholesaling step by step",budget:0.5},
    {name:"REITs Simplified",handle:"reit.simple",emoji:"📊",platforms:["youtube_shorts","x"],angle:"passive RE investing",budget:0.5},
    {name:"First Home Buyer",handle:"first.home",emoji:"🔑",platforms:["tiktok","instagram"],angle:"first home mistakes",budget:0.5},
  ],
  luxury: [
    {name:"Billionaire Habits",handle:"billionaire.habits",emoji:"🤑",platforms:["tiktok","youtube_shorts"],angle:"wealth habits",budget:0.5},
    {name:"Watch of the Day",handle:"watch.daily",emoji:"⌚",platforms:["instagram","tiktok"],angle:"iconic watches",budget:0.5},
    {name:"Supercar Spotter",handle:"supercar.spot",emoji:"🏎️",platforms:["tiktok","youtube_shorts"],angle:"street supercars",budget:0.5},
    {name:"Mansion Tour Daily",handle:"mansion.tour",emoji:"🏰",platforms:["tiktok","youtube_shorts"],angle:"crazy interiors",budget:0.5},
    {name:"First Class Flights",handle:"first.class",emoji:"🛫",platforms:["instagram","tiktok"],angle:"luxury travel",budget:0.5},
  ],
  motivation: [
    {name:"Hustle Quotes Daily",handle:"hustle.q",emoji:"💯",platforms:["instagram","tiktok"],angle:"raw grind quotes",budget:0.5},
    {name:"Comeback Stories",handle:"comeback.story",emoji:"🦁",platforms:["tiktok","youtube_shorts"],angle:"rags to riches",budget:0.5},
    {name:"Discipline > Motivation",handle:"discipline.daily",emoji:"⛓️",platforms:["tiktok","instagram"],angle:"daily discipline",budget:0.5},
    {name:"Sigma Rules",handle:"sigma.rules",emoji:"🐺",platforms:["tiktok","youtube_shorts"],angle:"unbothered mindset",budget:0.5},
    {name:"Millionaire Mindset",handle:"millionaire.mind",emoji:"💭",platforms:["tiktok","instagram"],angle:"money psychology",budget:0.5},
  ],
};

const ALL_NICHES = Object.keys(ACCOUNTS);

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "admin only" }, { status: 403 });

  const body = await req.json().catch(()=>({}));
  const only = Array.isArray(body.niches) && body.niches.length ? body.niches : ALL_NICHES;

  const admin = supabaseAdmin();
  let projectsCreated = 0, accountsCreated = 0;

  for (const slug of only) {
    if (!ACCOUNTS[slug]) continue;
    const emoji = NICHE_EMOJI[slug] || "📁";
    const name = slug.replace(/_/g," ").replace(/\b\w/g, (c:string)=>c.toUpperCase()) + " Portfolio";

    // Upsert project (by user_id + name)
    const existing = await admin.from("projects").select("id").eq("user_id", user.id).eq("name", name).maybeSingle();
    let pid;
    if (existing.data?.id) {
      pid = existing.data.id;
    } else {
      const { data: proj, error } = await admin.from("projects").insert({
        user_id: user.id, name, niche: slug,
        platforms: ["instagram","tiktok","youtube_shorts"],
        status: "active",
        cta: "Follow for one move a day.",
        daily_budget_usd: 2.50,
      }).select().single();
      if (error || !proj) continue;
      pid = proj.id;
      projectsCreated++;
    }

    let firstAccountInProject = true;
    for (const acc_def of ACCOUNTS[slug]) {
      const { data: existingAcc } = await admin.from("project_accounts")
        .select("id").eq("project_id", pid).eq("handle", acc_def.handle).maybeSingle();
      if (existingAcc?.id) { firstAccountInProject = false; continue; }
      // FIRST account of the ai_tools project starts ACTIVE; everything else starts PAUSED
      // so the user can start with 1 account as requested.
      const isFirst = slug === "ai_tools" && firstAccountInProject && projectsCreated === 0;
      const { error: insErr } = await admin.from("project_accounts").insert({
        project_id: pid, user_id: user.id,
        name: acc_def.name, handle: acc_def.handle,
        platforms: acc_def.platforms, niche: slug,
        status: isFirst ? "needs_setup" : "paused",
        avatar_emoji: acc_def.emoji,
        daily_budget_usd: acc_def.budget, posts_per_day: 1,
        paused: !isFirst,
        platforms_config: { angle: acc_def.angle },
      });
      if (!insErr) accountsCreated++;
      firstAccountInProject = false;
    }
  }

  return NextResponse.json({
    ok: true,
    niches: only.length,
    projects_created: projectsCreated,
    accounts_created: accountsCreated,
    next_step: `Seeded ${projectsCreated} projects / ${accountsCreated} accounts. ONLY AI Tool Daily is active — all other 104 accounts are paused (as requested). Architect + Strategist + Grader run on AI Tool Daily first.`,
  });
}
