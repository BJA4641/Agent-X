import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
const WEB_VERSION = "5.7.0";

// GET /api/version — web + worker version & liveness at a glance
export async function GET() {
  let worker: any = null;
  try {
    const admin = supabaseAdmin();
    const { data } = await admin.from("worker_health")
      .select("version,last_heartbeat_at,started_at,host")
      .order("last_heartbeat_at", { ascending: false }).limit(1).maybeSingle();
    if (data) {
      const age = Math.round(Date.now() / 1000 - Number(data.last_heartbeat_at || 0));
      worker = { version: data.version, heartbeat_age_s: age, alive: age < 120, host: data.host };
    }
  } catch { /* worker info best-effort */ }
  return NextResponse.json({ web: WEB_VERSION, worker });
}
