import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function GET() {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  const [{ data: w }, { data: tx }, { data: todaySpend }] = await Promise.all([
    admin.from("wallets").select("*").eq("user_id", user.id).maybeSingle(),
    admin.from("wallet_transactions").select("*").eq("user_id", user.id).order("created_at", { ascending: false }).limit(50),
    admin.from("wallet_transactions").select("amount").eq("user_id", user.id).eq("type", "consume")
      .gte("created_at", new Date(new Date().setHours(0,0,0,0)).toISOString()),
  ]);
  const balance = Number(w?.balance_usd || 0);
  const spent = (todaySpend || []).reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
  const topup = (tx || []).filter((r: any) => r.type !== "consume").reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
  return NextResponse.json({ balance, spent, topup, tx: tx || [] });
}
