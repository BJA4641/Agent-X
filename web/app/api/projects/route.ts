import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

// Multi-project: each row = one brand/page the agents plan for.
// RLS guarantees users only ever see their own projects.
export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const { data, error } = await sb.from("projects").select("*").order("created_at");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ projects: data || [] });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const body = await req.json();
  const action = String(body.action || "");

  if (action === "create") {
    const name = String(body.name || "").trim().slice(0, 60);
    const niche = String(body.niche || "").trim().slice(0, 40);
    if (!name) return NextResponse.json({ error: "Name required" }, { status: 400 });
    const { count } = await sb.from("projects").select("id", { count: "exact", head: true });
    if ((count || 0) >= 6) return NextResponse.json({ error: "Max 6 projects for now." }, { status: 400 });
    const { data, error } = await sb.from("projects")
      .insert({ user_id: user.id, name, niche: niche || null }).select().single();
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, project: data });
  }

  if (action === "set_active") {
    // "Selected" = which project YOUR hand-queued topics get tagged with.
    // The pipeline plans for ALL non-paused projects regardless.
    const id = String(body.id || "");
    const { data } = await sb.from("projects").select("id").eq("id", id).single();
    if (!data) return NextResponse.json({ error: "Not your project" }, { status: 403 });
    const res = NextResponse.json({ ok: true });
    res.cookies.set("ax_project", id, { maxAge: 60 * 60 * 24 * 365, path: "/" });
    return res;
  }

  if (action === "pause" || action === "resume") {
    const { error } = await sb.from("projects")
      .update({ status: action === "pause" ? "paused" : "active" }).eq("id", String(body.id || ""));
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true });
  }

  if (action === "delete") {
    const { error } = await sb.from("projects").delete().eq("id", String(body.id || ""));
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
