import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const { data } = await supabaseAdmin()
    .from("projects").select("id,name,niche,platforms,status,cta,created_at")
    .eq("user_id", user.id).order("created_at");
  return NextResponse.json({ projects: data || [] });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const { data, error } = await supabaseAdmin().from("projects").insert({
    user_id: user.id,
    name: String(body.name || "New project").slice(0, 80),
    niche: String(body.niche || "ai_tools").slice(0, 60),
    platforms: Array.isArray(body.platforms) ? body.platforms : ["instagram","tiktok"],
    cta: body.cta ? String(body.cta).slice(0,120) : null,
  }).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ project: data });
}

export async function DELETE(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await supabaseAdmin().from("projects").delete().eq("id", id).eq("user_id", user.id);
  return NextResponse.json({ ok: true });
}
