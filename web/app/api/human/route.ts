import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const TENANT = process.env.TENANT_ID || "me";

/** GET /api/human — list open escalations (admin only). */
export async function GET() {
  const sbServer = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sbServer.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "Admins only." }, { status: 403 });

  const { data, error } = await admin
    .from("escalations")
    .select("*")
    .is("resolved_at", null)
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ escalations: data || [] });
}

/** POST /api/human — resolve an escalation (approve/reject with note). */
export async function POST(req: Request) {
  const sbServer = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sbServer.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "Admins only." }, { status: 403 });

  const { id, resolution, note } = await req.json();
  if (!id || !resolution) return NextResponse.json({ error: "id + resolution required" }, { status: 400 });

  const now = new Date().toISOString();
  const { error } = await admin.from("escalations").update({
    resolution: String(resolution).slice(0,40),
    resolved_note: String(note||"").slice(0,500),
    resolved_by: user.id,
    resolved_at: now,
  }).eq("id", id).is("resolved_at", null);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
