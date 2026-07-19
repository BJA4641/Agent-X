import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function GET(_: Request, { params }: { params: Promise<{ pid: string }> }) {
  const { pid } = await params;
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });

  // Verify project ownership
  const proj = await supabaseAdmin().from("projects")
    .select("id").eq("id", pid).eq("user_id", user.id).single();
  if (!proj.data) return NextResponse.json({ error: "not found" }, { status: 404 });

  const { data } = await supabaseAdmin()
    .from("project_accounts").select("*,account_posts(status)")
    .eq("project_id", pid).order("created_at");
  return NextResponse.json({ accounts: data || [] });
}

export async function POST(req: Request, { params }: { params: Promise<{ pid: string }> }) {
  const { pid } = await params;
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const proj = await supabaseAdmin().from("projects")
    .select("id,niche").eq("id", pid).eq("user_id", user.id).single();
  if (!proj.data) return NextResponse.json({ error: "not found" }, { status: 404 });
  const body = await req.json().catch(() => ({}));
  const niche = proj.data.niche || body.niche || "ai_tools";
  const { data, error } = await supabaseAdmin().from("project_accounts").insert({
    project_id: pid, user_id: user.id,
    name: String(body.name || "New account").slice(0, 80),
    handle: String(body.handle || "new_account").slice(0,40).replace(/[^a-zA-Z0-9_]/g,"_"),
    platforms: Array.isArray(body.platforms) ? body.platforms : ["instagram","tiktok","youtube_shorts"],
    niche,
    status: "needs_setup",
    avatar_emoji: body.avatar_emoji || "🤖",
  }).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ account: data });
}
