// app/api/revenue/track/route.ts — v5.5 P0 affiliate/revenue pixel.
// Fires from affiliate network postbacks, link-in-bio redirects, or manual
// entry. Writes a revenue_events row so CEO ROI math uses real revenue.
import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!;

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { amount_usd, source, account_id, item_id, metadata, secret } = body || {};

    // Simple shared-secret auth so random internet can't spoof revenue
    const expected = process.env.REVENUE_WEBHOOK_SECRET;
    if (expected && secret !== expected) {
      return NextResponse.json({ ok: false, error: "bad secret" }, { status: 401 });
    }

    const amount = Number(amount_usd);
    if (!amount || amount <= 0) {
      return NextResponse.json({ ok: false, error: "amount_usd required >0" }, { status: 400 });
    }
    if (!source) {
      return NextResponse.json({ ok: false, error: "source required" }, { status: 400 });
    }

    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
    const { data, error } = await sb.from("revenue_events").insert({
      tenant_id: "me",
      account_id: account_id || null,
      item_id: item_id ? String(item_id) : null,
      amount_usd: Math.round(amount * 1e5) / 1e5,
      source: String(source).slice(0, 64),
      metadata: metadata || {},
    }).select("id").single();

    if (error) {
      return NextResponse.json({ ok: false, error: error.message }, { status: 500 });
    }
    return NextResponse.json({ ok: true, id: data.id });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message || e) }, { status: 500 });
  }
}

// Simple summary endpoint for CEO dashboard
export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const account_id = url.searchParams.get("account_id") || null;
    const days = parseInt(url.searchParams.get("days") || "30", 10);
    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
    let q = sb.from("revenue_events").select("amount_usd,source,created_at,account_id,item_id")
      .gte("created_at", new Date(Date.now() - days*86400000).toISOString());
    if (account_id) q = q.eq("account_id", account_id);
    const { data, error } = await q;
    if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 500 });
    const total = (data||[]).reduce((s, r) => s + Number(r.amount_usd||0), 0);
    const by_source: Record<string, number> = {};
    for (const r of (data||[])) by_source[r.source] = (by_source[r.source]||0) + Number(r.amount_usd||0);
    return NextResponse.json({ ok: true, total_usd: total, count: (data||[]).length, by_source });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: String(e?.message||e) }, { status: 500 });
  }
}
