import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { supabaseAdmin } from "@/lib/supabase/server";

// Public form on /agents. Service-role insert; RLS keeps leads private
// (only the referrer whose code is attached can read their own rows).
export async function POST(req: Request) {
  const b = await req.json().catch(() => ({}));
  if (String(b.website || "")) return NextResponse.json({ ok: true }); // honeypot: silently drop bots
  const name = String(b.name || "").trim().slice(0, 80);
  const email = String(b.email || "").trim().slice(0, 120);
  const agent_slug = String(b.agent_slug || "").trim().slice(0, 60);
  if (!name || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || !agent_slug)
    return NextResponse.json({ error: "Name, valid email and agent are required." }, { status: 400 });
  const row = {
    agent_slug, name, email,
    company: String(b.company || "").trim().slice(0, 120) || null,
    message: String(b.message || "").trim().slice(0, 1000) || null,
    ref_code: cookies().get("ax_ref")?.value?.slice(0, 16) || null,
  };
  const { error } = await supabaseAdmin().from("agent_leads").insert(row);
  if (error) return NextResponse.json({ error: "Could not save — try again." }, { status: 500 });
  return NextResponse.json({ ok: true });
}
