/**
 * POST /api/admin/seed-demo
 * Admin only — creates 6 niche projects × 5 accounts each for demo/testing.
 * All accounts start as needs_setup so the Architect agent picks them up on next tick.
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const NICHES: Record<string, { emoji: string; accounts: { name: string; handle: string; emoji: string; platforms: string[] }[] }> = {
  ai_tools: { emoji: "🤖", accounts: [
    { name: "AI Tool Daily", handle: "aitool_daily", emoji: "🤖", platforms: ["instagram","tiktok","youtube_shorts"] },
    { name: "Prompt Hacks", handle: "prompt.hacks", emoji: "✨", platforms: ["instagram","tiktok"] },
    { name: "Agent Lab", handle: "agentlab", emoji: "🧠", platforms: ["tiktok","youtube_shorts","x"] },
    { name: "Code Faster", handle: "codefaster", emoji: "💻", platforms: ["youtube_shorts","x"] },
    { name: "AI Money Moves", handle: "aimoney.moves", emoji: "💰", platforms: ["instagram","tiktok"] },
  ]},
  finance: { emoji: "💰", accounts: [
    { name: "Side Hustle Lab", handle: "sidehustle.lab", emoji: "💸", platforms: ["instagram","tiktok","youtube_shorts"] },
    { name: "Invest Simple", handle: "invest.simple", emoji: "📈", platforms: ["youtube_shorts","instagram"] },
    { name: "Budget Bro", handle: "budget.bro", emoji: "💵", platforms: ["tiktok","instagram"] },
    { name: "FIRE Diaries", handle: "fire.diaries", emoji: "🔥", platforms: ["youtube_shorts","x"] },
    { name: "Credit Fix", handle: "credit.fix", emoji: "💳", platforms: ["instagram","tiktok"] },
  ]},
  fitness: { emoji: "💪", accounts: [
    { name: "Home Gains", handle: "home.gains", emoji: "🏋️", platforms: ["instagram","tiktok","youtube_shorts"] },
    { name: "No Gym Fit", handle: "nogym.fit", emoji: "💪", platforms: ["tiktok","instagram"] },
    { name: "Protein Kitchen", handle: "protein.kitchen", emoji: "🥗", platforms: ["instagram","tiktok"] },
    { name: "Couch to 5k", handle: "couch25k", emoji: "🏃", platforms: ["youtube_shorts","instagram"] },
    { name: "Mobility Fix", handle: "mobility.fix", emoji: "🧘", platforms: ["instagram","tiktok"] },
  ]},
  cooking: { emoji: "🍳", accounts: [
    { name: "10 Min Meals", handle: "10min.meals", emoji: "⏱️", platforms: ["instagram","tiktok","youtube_shorts"] },
    { name: "Student Kitchen", handle: "student.kitchen", emoji: "🍜", platforms: ["tiktok","instagram"] },
    { name: "Protein Plate", handle: "protein.plate", emoji: "🥩", platforms: ["instagram","tiktok"] },
    { name: "Budget Bites", handle: "budget.bites", emoji: "🥪", platforms: ["tiktok","youtube_shorts"] },
    { name: "Air Fryer Life", handle: "airfryer.life", emoji: "🍟", platforms: ["instagram","tiktok"] },
  ]},
  saas: { emoji: "🚀", accounts: [
    { name: "Indie Hackers Daily", handle: "indie.daily", emoji: "🚀", platforms: ["x","linkedin","youtube_shorts"] },
    { name: "Micro SaaS Lab", handle: "microsaas.lab", emoji: "🔧", platforms: ["x","youtube_shorts"] },
    { name: "Launch Log", handle: "launch.log", emoji: "📊", platforms: ["x","linkedin"] },
    { name: "Pricing Teardown", handle: "pricing.teardown", emoji: "💲", platforms: ["linkedin","youtube_shorts"] },
    { name: "Cold Outbound AI", handle: "outbound.ai", emoji: "✉️", platforms: ["linkedin","x"] },
  ]},
  skincare: { emoji: "✨", accounts: [
    { name: "Glow Up Daily", handle: "glowup.daily", emoji: "✨", platforms: ["instagram","tiktok"] },
    { name: "Skin Science", handle: "skin.science", emoji: "🔬", platforms: ["youtube_shorts","instagram"] },
    { name: "Budget Skincare", handle: "budget.glow", emoji: "💄", platforms: ["tiktok","instagram"] },
    { name: "Acne Diaries", handle: "acne.diaries", emoji: "🧴", platforms: ["tiktok","instagram"] },
    { name: "SPF Everything", handle: "spf.everything", emoji: "☀️", platforms: ["instagram","tiktok"] },
  ]},
};

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "admin only" }, { status: 403 });

  const admin = supabaseAdmin();
  let projectsCreated = 0, accountsCreated = 0;

  for (const [slug, cfg] of Object.entries(NICHES)) {
    // Create project
    const { data: proj, error } = await admin.from("projects").upsert({
      user_id: user.id,
      name: slug.replace("_", " ").replace(/\b\w/g, (c: string) => c.toUpperCase()) + " Portfolio",
      niche: slug,
      platforms: ["instagram","tiktok","youtube_shorts"],
      status: "active",
      cta: "Follow for one move a day.",
    }, { onConflict: "user_id,name" }).select().single();
    if (error || !proj) continue;
    projectsCreated++;

    for (const acc_def of cfg.accounts) {
      const { data: existing } = await admin.from("project_accounts")
        .select("id").eq("project_id", proj.id).eq("handle", acc_def.handle).maybeSingle();
      if (existing) continue;
      await admin.from("project_accounts").insert({
        project_id: proj.id,
        user_id: user.id,
        name: acc_def.name,
        handle: acc_def.handle,
        platforms: acc_def.platforms,
        niche: slug,
        status: "needs_setup",
        avatar_emoji: acc_def.emoji,
      });
      accountsCreated++;
    }
  }

  return NextResponse.json({
    ok: true,
    projects_created: projectsCreated,
    accounts_created: accountsCreated,
    next_step: "The Architect agent will write brand docs on the next tick (~60s), then the Strategist plans 10 posts/account."
  });
}
