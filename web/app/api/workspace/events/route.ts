import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ events: [] });

  // If table doesn't exist yet, return empty array gracefully.
  try {
    const { data, error } = await sb.from("agent_events")
      .select("*").eq("user_id", user.id).order("created_at", { ascending: false }).limit(200);
    if (error) return NextResponse.json({ events: [], error: error.message });
    return NextResponse.json({ events: data || [] });
  } catch (e: any) {
    return NextResponse.json({ events: [] });
  }
}
