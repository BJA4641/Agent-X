import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const admin = supabaseAdmin();
  const { data } = await admin.from("profiles").select("*").eq("user_id", user.id).maybeSingle();
  return NextResponse.json(data || { onboarded: false });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const body = await req.json();
  const patch: any = {
    user_id: user.id,
    niche: body.niche || null,
    page_name: body.page_name || null,
    platforms: body.platforms || [],
    updated_at: new Date().toISOString(),
  };
  if (body.onboarded) { patch.onboarded = true; patch.onboarding_step = 3; }
  const { error } = await admin.from("profiles").upsert(patch, { onConflict: "user_id" });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  // Seed a starter wallet with $1 free credit
  const { data: existing } = await admin.from("wallets").select("user_id").eq("user_id", user.id).maybeSingle();
  if (!existing) {
    await admin.from("wallets").insert({ user_id: user.id, balance_usd: 1.0, lifetime_topup: 1.0 });
    await admin.from("wallet_transactions").insert({
      user_id: user.id, type: "bonus", amount: 1.0, note: "Welcome bonus",
    });
  }
  return NextResponse.json({ ok: true });
}
