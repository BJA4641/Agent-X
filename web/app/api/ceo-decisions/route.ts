import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const TENANT = process.env.TENANT_ID || "me";

export async function GET(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "admins only" }, { status: 403 });
  const url = new URL(req.url);
  const days = Number(url.searchParams.get("days") || 1);
  const since = new Date(); since.setDate(since.getDate() - days);
  const admin = supabaseAdmin();
  const [{ data: decisions }, { data: alloc }, { data: roi }, { data: recs }] = await Promise.all([
    admin.from("exec_decisions").select("*").eq("tenant_id", TENANT)
      .gte("created_at", since.toISOString()).order("ts", { ascending: false }).limit(200),
    admin.from("capital_allocation").select("*").eq("tenant_id", TENANT)
      .eq("day", new Date().toISOString().slice(0,10)),
    admin.from("roi_snapshots").select("*").eq("tenant_id", TENANT)
      .gte("day", since.toISOString().slice(0,10)).order("day", { ascending: false }).limit(30),
    admin.from("ceo_recommendations").select("*").eq("tenant_id", TENANT)
      .eq("dismissed", false).order("ts", { ascending: false }).limit(20),
  ]);
  const summary = {
    total_decisions: (decisions||[]).length,
    approved: (decisions||[]).filter(d=>d.decision==="approve").length,
    denied: (decisions||[]).filter(d=>d.decision==="deny").length,
    delayed: (decisions||[]).filter(d=>d.decision==="delay").length,
    reused: (decisions||[]).filter(d=>d.decision==="reuse").length,
    cheaper: (decisions||[]).filter(d=>d.decision==="cheaper").length,
    total_est_cost: (decisions||[]).reduce((a,d)=>a+Number(d.estimated_cost_usd||0),0),
    total_reuse_savings: (decisions||[]).filter(d=>d.decision==="reuse").reduce((a,d)=>a+Number(d.estimated_cost_usd||0),0),
  };
  return NextResponse.json({
    summary, decisions: decisions||[], allocations: alloc||[],
    roi: roi||[], recommendations: recs||[],
  });
}

export async function POST(req: Request) {
  // Apply or dismiss a recommendation
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "admins only" }, { status: 403 });
  const body = await req.json().catch(() => ({}));
  const { id, action } = body;
  if (!id) return NextResponse.json({ error: "id required" }, { status: 400 });
  const admin = supabaseAdmin();
  if (action === "dismiss") {
    await admin.from("ceo_recommendations").update({ dismissed: true }).eq("id", id);
  } else if (action === "apply") {
    await admin.from("ceo_recommendations").update({ applied: true }).eq("id", id);
  } else return NextResponse.json({ error: "unknown action" }, { status: 400 });
  return NextResponse.json({ ok: true });
}
