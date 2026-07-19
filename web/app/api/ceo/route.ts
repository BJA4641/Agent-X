import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const TENANT = process.env.TENANT_ID || "me";

/**
 * GET /api/ceo — CEO 1-page dashboard data.
 *
 * Returns a single JSON object with:
 *   budget:   {spent_usd, cap_usd, pct, autothrottle, killswitch}
 *   workers:  [{worker_id, last_heartbeat_at, jobs_completed, jobs_failed, in_progress, version, host}]
 *   pipeline: {queued, claimed, in_progress, wait_human, done_today, failed_today}
 *   board:    {idea, drafted, approved, scheduled, published, rejected, reported, failed}
 *   kpis:     {publishes_24h, views_24h, spend_24h}
 *   escalations_open: count
 * Admin-only (owner email).
 */
export async function GET() {
  const sbServer = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sbServer.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "Admins only." }, { status: 403 });

  const today = new Date(); today.setHours(0,0,0,0);
  const iso = today.toISOString();
  const epochDay = Math.floor(today.getTime()/1000);

  try {
    // --- budget ---
    const { data: budgetRows } = await admin
      .from("settings").select("key,value").eq("tenant_id", TENANT)
      .in("key", ["daily_budget","kill_switch","autothrottle"]);
    const settings = Object.fromEntries((budgetRows||[]).map(r => [r.key, r.value||{}]));
    const cap = Number((settings as any).daily_budget?.usd || process.env.DAILY_BUDGET_USD || "1.50");

    const { data: ledger } = await admin
      .from("run_ledger").select("cost_usd").gte("created_at", iso);
    const spent = (ledger||[]).reduce((s,r)=>s+Number(r.cost_usd||0),0);

    // --- workers ---
    const { data: workers } = await admin
      .from("worker_health").select("*").order("last_heartbeat_at",{ascending:false}).limit(10);

    // --- pipeline jobs ---
    const { data: jobs } = await admin.from("jobs").select("status,created_at");
    const pipeline: any = {queued:0,claimed:0,in_progress:0,wait_human:0,done_today:0,failed_today:0};
    for (const j of (jobs||[])) {
      if (["queued","claimed","in_progress","wait_human"].includes(j.status)) pipeline[j.status] = (pipeline[j.status]||0)+1;
      if (j.status==="done" && (j.created_at||0) > epochDay) pipeline.done_today += 1;
      if (j.status==="failed" && (j.created_at||0) > epochDay) pipeline.failed_today += 1;
    }

    // --- board ---
    const { data: board } = await admin.from("board_items").select("status,created_at");
    const brd: any = {idea:0,drafted:0,approved:0,scheduled:0,published:0,rejected:0,reported:0,failed:0};
    for (const b of (board||[])) { if (brd[b.status] !== undefined) brd[b.status]++; }
    const publishes_24h = (board||[]).filter(b=>b.status==="published" && new Date(b.created_at)>=today).length;

    // --- views ---
    const { data: perf } = await admin.from("performance").select("views,likes,comments").gte("captured_at",iso);
    const views_24h = (perf||[]).reduce((s,r)=>s+Number(r.views||0),0);

    // --- escalations ---
    const { count: escCount, error: ec } = await admin
      .from("escalations").select("id",{count:"exact",head:true}).is("resolved_at",null);

    return NextResponse.json({
      budget: {
        spent_usd: +spent.toFixed(4), cap_usd: cap,
        pct: +((spent/cap)*100).toFixed(1),
        autothrottle: (settings as any).autothrottle || {on:true,reserve_fraction:0.1},
        killswitch: !!((settings as any).kill_switch?.on),
      },
      workers: workers || [],
      pipeline,
      board: brd,
      kpis: { publishes_24h, views_24h, spend_24h: +spent.toFixed(4) },
      escalations_open: escCount ?? 0,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
