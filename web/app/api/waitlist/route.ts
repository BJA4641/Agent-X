import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";

export async function POST(req: Request) {
  const { email } = await req.json();
  if (!email || !String(email).includes("@"))
    return NextResponse.json({ error: "Enter a valid email." }, { status: 400 });
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY)
    return NextResponse.json({ error: "Waitlist isn't configured yet (Supabase keys missing)." }, { status: 503 });
  const { error } = await supabaseAdmin().from("waitlist").upsert({ email: String(email).toLowerCase().trim() });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true });
}
