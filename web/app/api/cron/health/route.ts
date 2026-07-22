// =====================================================================
// Agent-X v6.0 BATCH 1 — WATCHDOG (the thing that ends 63-hour silent
// outages and money-burn-for-nothing, forever)
//
// Runs every 5 minutes via Vercel Cron. Checks four conditions:
//   1. DEAD WORKER      — heartbeat older than 5 minutes
//   2. FAILURE STORM    — >20 failed jobs in the last hour
//   3. BUDGET BREACH    — spend today > DAILY_BUDGET_USD
//   4. BURN-FOR-NOTHING — spend >$0.50 in 24h with ZERO items reaching
//                         approved/scheduled/published (your exact complaint)
//
// On any trip: writes a critical agent_events row (visible in dashboard)
// and POSTs to ALERT_WEBHOOK_URL if set (works with Discord webhook,
// Slack webhook, or any endpoint — payload includes both `content` and
// `text` keys). Alerts are muted for 30 min after firing to avoid spam.
//
// ENV NEEDED (Vercel): SUPABASE_URL, SUPABASE_SERVICE_KEY (already set),
//   DAILY_BUDGET_USD (optional, default 1.50),
//   ALERT_WEBHOOK_URL (optional but strongly recommended —
//   Discord: Server Settings -> Integrations -> Webhooks -> New -> copy URL)
// =====================================================================
import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

const TENANT = process.env.TENANT_ID || "me";

function sb() {
  return createClient(
    process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || ""
  );
}

async function notify(db: any, alerts: string[]) {
  const msg = "🚨 AGENT-X WATCHDOG 🚨\n" + alerts.map((a) => "• " + a).join("\n");

  // 1) Always leave a visible trail in the dashboard activity feed
  try {
    await db.from("agent_events").insert({
      agent: "watchdog",
      msg,
      level: "critical",
      kind: "alert",
    });
  } catch {}

  // 2) Push notification if a webhook is configured
  const hook = process.env.ALERT_WEBHOOK_URL;
  if (hook) {
    try {
      await fetch(hook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: msg.slice(0, 1900), text: msg.slice(0, 1900) }),
      });
    } catch {}
  }

  // 3) Mute repeat alerts for 30 minutes
  try {
    await db.from("settings").upsert(
      {
        tenant_id: TENANT,
        key: "watchdog_mute_until",
        value: { until: Date.now() + 30 * 60 * 1000 },
        updated_at: new Date().toISOString(),
      },
      { onConflict: "tenant_id,key" }
    );
  } catch {}
}

export async function GET() {
  const db = sb();
  const alerts: string[] = [];
  const status: Record<string, any> = {};
  const now = Date.now();

  // Respect mute window
  try {
    const { data: mute } = await db
      .from("settings")
      .select("value")
      .eq("tenant_id", TENANT)
      .eq("key", "watchdog_mute_until")
      .maybeSingle();
    const until = Number((mute?.value as any)?.until || 0);
    if (until > now) {
      return NextResponse.json({ ok: true, muted_for_s: Math.round((until - now) / 1000) });
    }
  } catch {}

  // ---- CHECK 1: dead worker (worker_health.last_heartbeat_at is epoch seconds)
  try {
    const { data } = await db
      .from("worker_health")
      .select("last_heartbeat_at,version")
      .order("last_heartbeat_at", { ascending: false })
      .limit(1);
    const hb = Number(data?.[0]?.last_heartbeat_at || 0);
    const ageMin = hb ? (now / 1000 - hb) / 60 : Infinity;
    status.heartbeat_age_min = Math.round(ageMin * 10) / 10;
    if (ageMin > 5) alerts.push(`Worker heartbeat is ${Math.round(ageMin)} min old — worker is DOWN or stalled (v${data?.[0]?.version || "?"})`);
  } catch (e: any) {
    status.heartbeat_check_error = String(e?.message || e);
  }

  // ---- CHECK 2: failure storm (jobs.created_at is epoch-float text)
  try {
    const hourAgo = String(now / 1000 - 3600);
    const { count } = await db
      .from("jobs")
      .select("id", { count: "exact", head: true })
      .eq("status", "failed")
      .gte("created_at", hourAgo);
    status.failed_last_hour = count ?? 0;
    if ((count ?? 0) > 20) alerts.push(`FAILURE STORM: ${count} jobs failed in the last hour — check Railway logs, likely a repeating error`);
  } catch (e: any) {
    status.failure_check_error = String(e?.message || e);
  }

  // ---- CHECK 3: budget breach (run_ledger.created_at is timestamptz)
  const dayAgoISO = new Date(now - 24 * 3600 * 1000).toISOString();
  let spend24h = 0;
  try {
    const { data } = await db.from("run_ledger").select("cost_usd").gte("created_at", dayAgoISO);
    spend24h = (data || []).reduce((s: number, r: any) => s + Number(r.cost_usd || 0), 0);
    status.spend_24h_usd = Math.round(spend24h * 10000) / 10000;
    const budget = Number(process.env.DAILY_BUDGET_USD || 1.5);
    if (spend24h > budget) alerts.push(`BUDGET BREACH: $${spend24h.toFixed(2)} spent in 24h vs $${budget.toFixed(2)} budget`);
  } catch (e: any) {
    status.budget_check_error = String(e?.message || e);
  }

  // ---- CHECK 4: burn-for-nothing (spend with zero real output)
  try {
    const { count } = await db
      .from("board_items")
      .select("id", { count: "exact", head: true })
      .in("status", ["approved", "scheduled", "published"])
      .gte("created_at", dayAgoISO);
    status.output_items_24h = count ?? 0;
    if (spend24h > 0.5 && (count ?? 0) === 0) {
      alerts.push(`BURNING MONEY FOR NOTHING: $${spend24h.toFixed(2)} spent in 24h with ZERO items reaching approved/published. Pause the account and investigate NOW.`);
    }
  } catch (e: any) {
    status.output_check_error = String(e?.message || e);
  }

  if (alerts.length) await notify(db, alerts);
  return NextResponse.json({ ok: alerts.length === 0, alerts, status, checked_at: new Date().toISOString() });
}
