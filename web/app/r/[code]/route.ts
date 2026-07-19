import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";

// Referral entry: log the click, remember the code for 30 days, land on /agents.
export async function GET(req: Request, { params }: { params: { code: string } }) {
  const code = String(params.code || "").slice(0, 16);
  const url = new URL(req.url);
  const slug = url.searchParams.get("a") || null;
  try {
    const admin = supabaseAdmin();
    const { data } = await admin.from("affiliate_links").select("code").eq("code", code).single();
    if (data) await admin.from("affiliate_clicks").insert({ code, agent_slug: slug });
  } catch {}
  const dest = new URL("/agents" + (slug ? `?a=${encodeURIComponent(slug)}` : ""), url.origin);
  const res = NextResponse.redirect(dest);
  res.cookies.set("ax_ref", code, { maxAge: 60 * 60 * 24 * 30, path: "/" });
  return res;
}
