/**
 * POST /api/projects/[pid]/generate
 * Manually queue a content generation for this project.
 *   { account_id?: string, topic?: string, count?: number }
 * Inserts rows directly into board_items (pipeline picks them up on next tick).
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function POST(req: Request, { params }: { params: { pid: string } }) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const { pid } = params;
  const admin = supabaseAdmin();
  const { data: proj } = await admin.from("projects")
    .select("id,user_id,paused,niche").eq("id", pid).single();
  if (!proj || proj.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });
  if (proj.paused) return NextResponse.json({ error: "project is paused — resume first" }, { status: 400 });

  const body = await req.json().catch(() => ({}));
  const accountId = body.account_id || null;
  const topic = String(body.topic || "").trim() || null;
  const count = Math.max(1, Math.min(5, parseInt(body.count) || 1));

  // If account specified, verify it belongs to this project and is not paused
  if (accountId) {
    const { data: acc } = await admin.from("project_accounts")
      .select("id,paused,project_id,status").eq("id", accountId).single();
    if (!acc || acc.project_id !== pid) return NextResponse.json({ error: "account not in project" }, { status: 400 });
    if (acc.paused) return NextResponse.json({ error: "account is paused — resume first" }, { status: 400 });
  }

  const inserted: any[] = [];
  for (let i = 0; i < count; i++) {
    const { data, error } = await admin.from("board_items").insert({
      tenant_id: "me",
      status: "idea",
      topic: topic || `${proj.niche.replace(/_/g," ")} tip #${Date.now()+i}`,
      payload: {
        project_id: pid,
        account_id: accountId,
        manual_trigger: true,
        requested_by: user.id,
        bucket: "manual",
      },
    }).select().single();
    if (data) inserted.push(data);
  }

  return NextResponse.json({ queued: inserted.length, items: inserted.map(i => i.id) });
}
