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
  // v5.10.5 REQ-BANNER-DIAG — when the banner says something is wrong, it must
  // say WHAT. Previously it reported "worker is not beating" with no way to tell
  // whether the worker was dead, the row was stale, or the web was reading a
  // different row entirely. These fields make that answerable in one page load.
  let diag: any = { server_time_s: Math.round(Date.now() / 1000) };
  try {
    const admin = supabaseAdmin();
    const { data: rows } = await admin.from("worker_health")
      .select("worker_id,version,last_heartbeat_at,host");
    diag.worker_rows = (rows || []).length;
    diag.workers = (rows || []).map((r: any) => ({
      id: r.worker_id, version: r.version, host: r.host,
      raw_heartbeat: Number(r.last_heartbeat_at || 0),
      age_s: Math.round(Date.now() / 1000 - Number(r.last_heartbeat_at || 0)),
    }));
    const keys = ["free_ladder_report", "escalation_last", "heartbeat_pulse", "cost_per_post"];
    const { data: st } = await admin.from("settings").select("key,value").in("key", keys);
    for (const row of st || []) diag[(row as any).key] = (row as any).value;
    // last failing agent — the single most useful line when something breaks
    const { data: errs } = await admin.from("agent_events")
      .select("agent,action,message,created_at,status")
      .in("status", ["error", "critical"])
      .order("created_at", { ascending: false }).limit(3);
    diag.recent_errors = (errs || []).map((e: any) => ({
      agent: e.agent, action: e.action, at: e.created_at,
      message: String(e.message || "").slice(0, 300),
    }));
    const { data: jf } = await admin.from("jobs")
      .select("job_type,error,created_at").eq("status", "failed")
      .order("created_at", { ascending: false }).limit(3);
    diag.recent_failed_jobs = (jf || []).map((j: any) => ({
      job_type: j.job_type, error: String(j.error || "").slice(0, 300),
    }));
  } catch (e: any) {
    diag.error = String(e?.message || e).slice(0, 200);
  }

  const commit = process.env.VERCEL_GIT_COMMIT_SHA || null;
  return NextResponse.json({ web: WEB_VERSION, commit, worker, cost_mode, diag },
    { headers: { "Cache-Control": "no-store, max-age=0" } });
}
