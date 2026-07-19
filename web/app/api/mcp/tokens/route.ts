import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import crypto from "crypto";

function genToken() {
  return "axmcp_" + crypto.randomBytes(24).toString("base64url");
}

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login required" }, { status: 401 });
  const { data } = await supabaseAdmin().from("mcp_connections")
    .select("id,provider,label,last_used_at,created_at,scopes")
    .eq("user_id", user.id).is("revoked_at", null).order("created_at");
  return NextResponse.json({ connections: data || [] });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login required" }, { status: 401 });
  const body = await req.json().catch(() => ({}));
  const provider = String(body.provider || "custom").slice(0, 40);
  const label = String(body.label || provider).slice(0, 80);
  const token = genToken();
  const { error } = await supabaseAdmin().from("mcp_connections").insert({
    user_id: user.id, provider, label, access_token: token,
    scopes: ["content.queue", "content.approve", "feed.read", "wallet.read", "projects.read", "kill_switch"]
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ token });
}

export async function DELETE(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login required" }, { status: 401 });
  const url = new URL(req.url);
  const id = url.searchParams.get("id");
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  await supabaseAdmin().from("mcp_connections")
    .update({ revoked_at: new Date().toISOString() })
    .eq("id", id).eq("user_id", user.id);
  return NextResponse.json({ revoked: true });
}
