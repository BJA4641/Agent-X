import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// v5.8.9 — GET /api/projects/accounts-summary
// Tiny endpoint behind the "no account is active" advisory. Counts only; no
// account rows leave the server.
export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });

  try {
    const admin = supabaseAdmin();
    const { data } = await admin.from("project_accounts").select("status");
    const rows = data || [];
    const by = (s: string) => rows.filter((r: any) => r.status === s).length;
    const counts = {
      active: by("active"),
      paused: by("paused"),
      ready: by("ready"),
      other: rows.length - by("active") - by("paused") - by("ready"),
      total: rows.length,
    };
    return NextResponse.json({ counts });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || "failed" }, { status: 500 });
  }
}
