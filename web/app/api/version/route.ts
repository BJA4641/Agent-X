import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
// v5.9.8 REQ-VERSION-1: read the SINGLE source of truth (repo-root version.json)
// instead of a hardcoded string. The old constant was never bumped after 5.9.4,
// so the banner honestly reported "5.9.4" while 5.9.7 was live on the worker —
// which made every deploy look like it had failed.
import versionFile from "@/version.json";
const WEB_VERSION = (versionFile as { version: string }).version;

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
  let cost_mode: string | null = null;
  try {
    const admin = supabaseAdmin();
    const { data } = await admin.from("settings").select("value").eq("key", "cost_mode").maybeSingle();
    cost_mode = (data?.value as any)?.mode ?? "normal";
  } catch { /* best effort */ }
  const commit = process.env.VERCEL_GIT_COMMIT_SHA || null;
  return NextResponse.json({ web: WEB_VERSION, commit, worker, cost_mode });
}
