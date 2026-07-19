import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

/** GET /api/workers — worker liveness status for admin dashboard. */
export async function GET() {
  const sbServer = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sbServer.auth.getUser();
  if (!user) return NextResponse.json({ workers: [] });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "Admins only." }, { status: 403 });

  const { data } = await admin.from("worker_health")
    .select("*").order("last_heartbeat_at", {ascending:false}).limit(20);
  // Mark stale workers (no heartbeat > 90s)
  const now = Date.now()/1000;
  const workers = (data||[]).map(w => ({
    ...w,
    alive: (w.last_heartbeat_at||0) > now - 90,
    seconds_since_hb: Math.max(0, Math.round(now - (w.last_heartbeat_at||0))),
  }));
  return NextResponse.json({ workers });
}
