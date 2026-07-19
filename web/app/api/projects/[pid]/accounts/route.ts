import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

// GET /api/projects/[pid]/accounts — list accounts for a project (with post counts)
export async function GET(req: Request, { params }: { params: { pid: string } }) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const { pid } = params;
  // Verify ownership
  const { data: proj } = await supabaseAdmin().from("projects")
    .select("id,user_id").eq("id", pid).single();
  if (!proj || proj.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });

  const { data } = await supabaseAdmin()
    .from("project_accounts")
    .select(`id,name,handle,niche,platforms,status,avatar_emoji,created_at,paused,daily_budget_usd,posts_per_day,platforms_config,
             account_posts(id,status)`)
    .eq("project_id", pid).order("created_at");
  return NextResponse.json({ accounts: data || [] });
}

// POST /api/projects/[pid]/accounts — add an account
export async function POST(req: Request, { params }: { params: { pid: string } }) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const { pid } = params;
  const { data: proj } = await supabaseAdmin().from("projects")
    .select("id,user_id,niche").eq("id", pid).single();
  if (!proj || proj.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });

  const body = await req.json().catch(() => ({}));
  const name = String(body.name || "New account").slice(0, 80);
  const handle = String(body.handle || name.toLowerCase().replace(/\s+/g, "_")).replace(/^@/, "").slice(0, 60);
  const niche = String(body.niche || proj.niche || "ai_tools").slice(0, 60);
  const platforms = Array.isArray(body.platforms) ? body.platforms : ["instagram","tiktok"];
  const emoji = String(body.avatar_emoji || "🤖").slice(0, 4);

  const { data, error } = await supabaseAdmin().from("project_accounts").insert({
    project_id: pid, user_id: user.id,
    name, handle, niche, platforms, avatar_emoji: emoji,
    status: "needs_setup",
    daily_budget_usd: 0.5, posts_per_day: 1,
    paused: true, // start paused so user can manually resume
    platforms_config: body.platforms_config || {},
  }).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ account: data });
}
