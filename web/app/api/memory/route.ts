/**
 * POST /api/memory — user sends a guidance message to the agents for a specific account/project.
 *   { account_id?, project_id?, content }
 * GET /api/memory?account_id=...&project_id=... — list recent memory.
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function GET(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const url = new URL(req.url);
  const accountId = url.searchParams.get("account_id");
  const projectId = url.searchParams.get("project_id");

  let q = supabaseAdmin().from("memory_entries").select("*").order("created_at", { ascending: false }).limit(50);
  if (accountId) {
    // verify ownership
    const { data: acc } = await supabaseAdmin().from("project_accounts")
      .select("user_id").eq("id", accountId).single();
    if (!acc || acc.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });
    q = q.eq("account_id", accountId);
  } else if (projectId) {
    const { data: proj } = await supabaseAdmin().from("projects")
      .select("user_id").eq("id", projectId).single();
    if (!proj || proj.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });
    q = q.eq("project_id", projectId);
  } else {
    return NextResponse.json({ error: "account_id or project_id required" }, { status: 400 });
  }
  const { data } = await q;
  return NextResponse.json({ memory: (data || []).reverse() });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const content = String(body.content || "").trim();
  if (!content) return NextResponse.json({ error: "content required" }, { status: 400 });
  const accountId = body.account_id || null;
  const projectId = body.project_id || null;
  if (!accountId && !projectId) return NextResponse.json({ error: "account_id or project_id required" }, { status: 400 });

  // verify ownership
  if (accountId) {
    const { data: acc } = await supabaseAdmin().from("project_accounts")
      .select("user_id").eq("id", accountId).single();
    if (!acc || acc.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  if (projectId) {
    const { data: proj } = await supabaseAdmin().from("projects")
      .select("user_id").eq("id", projectId).single();
    if (!proj || proj.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  const { data, error } = await supabaseAdmin().from("memory_entries").insert({
    account_id: accountId,
    project_id: projectId,
    role: "user",
    content: content.slice(0, 2000),
    metadata: { from: "user_chat" },
  }).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ entry: data });
}
