import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ events: [] });

  try {
    // Return BOTH system-wide events (agents talking = user_id IS NULL, scoped to tenant_id='me')
    // AND the user's own events. The pipeline writes everything with user_id=NULL so it
    // appears in every admin/owner feed.
    const { data, error } = await sb
      .from("agent_events")
      .select("*")
      .or(`user_id.eq.${user.id},and(user_id.is.null,tenant_id.eq.me)`)
      .order("created_at", { ascending: false })
      .limit(200);
    if (error) {
      console.warn("[workspace/events] error:", error.message);
      return NextResponse.json({ events: [], error: error.message });
    }
    return NextResponse.json({ events: data || [] });
  } catch (e: any) {
    return NextResponse.json({ events: [] });
  }
}
