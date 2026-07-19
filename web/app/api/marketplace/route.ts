import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

function randomCode() {
  let s = "";
  while (s.length < 8) s += Math.random().toString(36).slice(2);
  return s.slice(0, 8);
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const admin = supabaseAdmin();

  // public catalog for the /agents landing page — no auth, no personal data
  if (url.searchParams.get("public") === "1") {
    const { data } = await admin.from("marketplace_agents").select(
      "slug,name,tagline,description,category,price_usd,capabilities,demo_script")
      .eq("active", true).order("price_usd");
    return NextResponse.json({ agents: data || [] });
  }

  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  const { data: agents } = await admin.from("marketplace_agents").select("*").eq("active", true).order("price_usd");

  // ensure the user has an affiliate code (one per account)
  let { data: link } = await sb.from("affiliate_links").select("code").single();
  if (!link) {
    for (let i = 0; i < 3 && !link; i++) {
      const { data, error } = await admin.from("affiliate_links")
        .insert({ user_id: user.id, code: randomCode() }).select("code").single();
      if (!error) link = data; // retry on the (tiny) chance of a code collision
    }
  }

  // referrer stats — RLS lets the user see only their own clicks/leads
  const code = link?.code || null;
  let clicks = 0, leads: any[] = [];
  if (code) {
    const { count } = await sb.from("affiliate_clicks").select("id", { count: "exact", head: true }).eq("code", code);
    clicks = count || 0;
    const { data: l } = await sb.from("agent_leads")
      .select("agent_slug,status,sale_usd,commission_usd,commission_paid,created_at")
      .eq("ref_code", code).order("created_at", { ascending: false }).limit(50);
    leads = l || [];
  }
  return NextResponse.json({ agents: agents || [], code, clicks, leads });
}
