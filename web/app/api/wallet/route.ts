import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

export async function GET() {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  const [{ data: w }, { data: tx }, { data: todaySpend }, { data: todayRunSpend }] = await Promise.all([
    admin.from("wallets").select("*").eq("user_id", user.id).maybeSingle(),
    admin.from("wallet_transactions").select("*").eq("user_id", user.id).order("created_at", { ascending: false }).limit(50),
    admin.from("wallet_transactions").select("amount").eq("user_id", user.id).eq("type", "consume")
      .gte("created_at", new Date(new Date().setHours(0,0,0,0)).toISOString()),
    // v5.3 FIX: also read actual pipeline spend from run_ledger (which is where
    // the worker records LLM/render costs). The wallet_transactions table tracks
    // demo wallet topups; run_ledger tracks real API spend.
    isAdmin(user.email)
      ? admin.from("run_ledger").select("cost_usd")
          .gte("created_at", new Date(new Date().setHours(0,0,0,0)).toISOString())
      : Promise.resolve({ data: [] }),
  ]);
  const balance = Number(w?.balance_usd || 0);
  const walletSpent = (todaySpend || []).reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
  const pipelineSpent = (todayRunSpend || []).reduce((a: number, r: any) => a + Number(r.cost_usd || 0), 0);
  // For admin/founder view, show the REAL pipeline spend; for regular users, show wallet spend.
  const spent = isAdmin(user.email) ? pipelineSpent : walletSpent;
  const topup = (tx || []).filter((r: any) => r.type !== "consume").reduce((a: number, r: any) => a + Number(r.amount || 0), 0);
  return NextResponse.json({
    balance, spent, topup, tx: tx || [],
    pipeline_spent: +pipelineSpent.toFixed(4),
    wallet_spent: +walletSpent.toFixed(4),
    is_admin: isAdmin(user.email),
  });
}
