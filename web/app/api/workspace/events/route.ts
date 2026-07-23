import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ events: [] });

  try {
    // Return BOTH system-wide events (agents talking = user_id IS NULL, scoped to tenant_id='me')
    // AND the user's own events. The pipeline writes everything with user_id=NULL so it
    // appears in every admin/owner feed.
    const { data, error } = await sb
      .from("agent_events")
      .select("*")
      .or(`user_id.eq.${user.id},and(user_id.is.null,tenant_id.eq.me)`)
      .order("created_at", { ascending: false })
      .limit(200);
    if (error) {
      console.warn("[workspace/events] error:", error.message);
      return NextResponse.json({ events: [], error: error.message });
    }
    // v5.10.5 REQ-SPEND-DISPLAY: the workspace summed events[].cost_usd, but
    // agent_events has no cost column — costs live in run_ledger. The Spend card
    // therefore read $0.000 while the ledger held $1.27. Return the real figures.
    let spend = { today_usd: 0, all_time_usd: 0, paid_calls_today: 0 };
    try {
      const startOfDay = new Date(); startOfDay.setUTCHours(0, 0, 0, 0);
      const { data: led } = await sb.from("run_ledger")
        .select("cost_usd, created_at, model").gte("created_at", startOfDay.toISOString());
      const rows = led || [];
      spend.today_usd = rows.reduce((a: number, r: any) => a + Number(r.cost_usd || 0), 0);
      spend.paid_calls_today = rows.filter((r: any) => Number(r.cost_usd || 0) > 0).length;
      const { data: all } = await sb.from("run_ledger").select("cost_usd");
      spend.all_time_usd = (all || []).reduce((a: number, r: any) => a + Number(r.cost_usd || 0), 0);
    } catch { /* spend is best-effort; the feed must still render */ }
    return NextResponse.json({ events: data || [], spend });
  } catch (e: any) {
    return NextResponse.json({ events: [] });
  }
}
