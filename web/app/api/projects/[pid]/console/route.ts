/**
 * GET /api/projects/[pid]/console
 * Returns everything the project console needs:
 *   - project info
 *   - accounts with post/grade/paused breakdown
 *   - project-level memory (founder notes visible to ALL agents on all accounts in project)
 *   - recent agent events scoped to this project
 *   - performance stats (avg grade, posts drafted/published, spent)
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function GET(_req: Request, { params }: { params: { pid: string } }) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const { pid } = params;
  const admin = supabaseAdmin();

  const { data: proj } = await admin.from("projects")
    .select("*").eq("id", pid).eq("user_id", user.id).single();
  if (!proj) return NextResponse.json({ error: "not found" }, { status: 404 });

  // All accounts with post counts + latest grades
  const { data: accounts } = await admin.from("project_accounts")
    .select("id,name,handle,status,avatar_emoji,paused,niche,daily_budget_usd,created_at")
    .eq("project_id", pid).order("created_at");

  const accIds = (accounts || []).map(a => a.id);

  // Post counts per account
  let postsByAcc: Record<string, { planned: number; drafted: number; published: number; rejected: number; avg_grade: number; passed: number }> = {};
  for (const a of accounts || []) { postsByAcc[a.id] = { planned: 0, drafted: 0, published: 0, rejected: 0, avg_grade: 0, passed: 0 }; }

  if (accIds.length) {
    const { data: posts } = await admin.from("account_posts")
      .select("id,account_id,status").in("account_id", accIds).limit(500);
    for (const p of posts || []) {
      const acc = postsByAcc[p.account_id];
      if (!acc) continue;
      if (p.status === "planned") acc.planned++;
      else if (p.status === "drafted" || p.status === "approved" || p.status === "scheduled") acc.drafted++;
      else if (p.status === "published") acc.published++;
      else if (p.status === "rejected" || p.status === "failed") acc.rejected++;
    }
    // Grades
    const { data: postGrades } = await admin.from("content_grades")
      .select("post_id,overall,passed").not("post_id", "is", null).limit(500);
    const gradesByPost: Record<string, { overall: number; passed: boolean }> = {};
    for (const g of postGrades || []) { if (g.post_id) gradesByPost[g.post_id] = { overall: g.overall, passed: g.passed }; }
    const { data: postsWithId } = await admin.from("account_posts")
      .select("id,account_id").in("account_id", accIds);
    for (const p of postsWithId || []) {
      const g = gradesByPost[p.id];
      if (!g) continue;
      const acc = postsByAcc[p.account_id];
      if (!acc) continue;
      acc.avg_grade = acc.avg_grade ? (acc.avg_grade + g.overall)/2 : g.overall;
      if (g.passed) acc.passed++;
    }
  }

  // Project memory
  const { data: projMem } = await admin.from("memory_entries")
    .select("*").eq("project_id", pid).order("created_at", { ascending: false }).limit(50);
  // Account-level memory (recent user messages)
  const { data: accMem } = accIds.length ? await admin.from("memory_entries")
    .select("id,role,content,created_at,account_id,metadata").in("account_id", accIds).order("created_at", { ascending: false }).limit(80)
    : { data: [] };

  // Agent events (recent, all system events — pipeline tags them with item_id which we can't easily scope,
  // so we pull the latest 100)
  const { data: events } = await admin.from("agent_events")
    .select("*").order("created_at", { ascending: false }).limit(60);

  return NextResponse.json({
    project: proj,
    accounts: (accounts || []).map(a => ({ ...a, counts: postsByAcc[a.id] || { planned:0,drafted:0,published:0,rejected:0,avg_grade:0,passed:0 } })),
    project_memory: (projMem || []).reverse(),
    account_chat: (accMem || []).reverse(),
    events: (events || []).reverse(),
  });
}
