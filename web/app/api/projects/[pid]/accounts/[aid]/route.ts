import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

type Ctx = { params: { pid: string; aid: string } };

async function verifyOwnership(pid: string, aid: string) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { error: "login", status: 401 as const };
  const admin = supabaseAdmin();
  const { data: proj } = await admin.from("projects")
    .select("id,user_id").eq("id", pid).single();
  if (!proj || proj.user_id !== user.id) return { error: "project not found", status: 404 as const };
  const { data: acc } = await admin.from("project_accounts")
    .select("id,project_id,user_id").eq("id", aid).eq("project_id", pid).single();
  if (!acc || acc.user_id !== user.id) return { error: "account not found", status: 404 as const };
  return { user, admin };
}

// GET /api/projects/[pid]/accounts/[aid] — documents + posts + grades
export async function GET(_req: Request, { params }: Ctx) {
  const v = await verifyOwnership(params.pid, params.aid);
  if ("error" in v) return NextResponse.json({ error: v.error }, { status: v.status });
  const { admin } = v;
  const [{ data: docs }, { data: posts }, { data: grades }, { data: acc }, { data: mem }] = await Promise.all([
    admin.from("account_documents").select("*").eq("account_id", params.aid).order("doc_type"),
    admin.from("account_posts").select("*").eq("account_id", params.aid).order("created_at", { ascending: false }).limit(30),
    admin.from("content_grades").select("*").order("created_at", { ascending: false }).limit(30),
    admin.from("project_accounts").select("id,name,handle,niche,platforms,status,avatar_emoji,paused,daily_budget_usd,posts_per_day,config,platforms_config,created_at").eq("id", params.aid).single(),
    admin.from("memory_entries").select("id,role,content,created_at,metadata").eq("account_id", params.aid).order("created_at", { ascending: false }).limit(50),
  ]);
  // Attach latest grade to each post
  const gradeByPost: Record<string, any> = {};
  for (const g of grades || []) {
    if (g.post_id && !gradeByPost[g.post_id]) gradeByPost[g.post_id] = g;
  }
  const postsWithGrades = (posts || []).map(p => ({ ...p, grade: gradeByPost[p.id] || null }));
  return NextResponse.json({
    account: acc, project: { id: params.pid },
    documents: Object.fromEntries((docs || []).map(d => [d.doc_type, d])),
    posts: postsWithGrades,
    memory: (mem || []).reverse(),
  });
}

// PATCH /api/projects/[pid]/accounts/[aid] — toggle paused / update budget / rename
export async function PATCH(req: Request, { params }: Ctx) {
  const v = await verifyOwnership(params.pid, params.aid);
  if ("error" in v) return NextResponse.json({ error: v.error }, { status: v.status });
  const { admin } = v;
  const body = await req.json().catch(() => ({}));
  const patch: Record<string, any> = {};
  if (body.paused !== undefined) {
    patch.paused = !!body.paused;
    if (patch.paused) patch.status = "paused";
  }
  if (body.daily_budget_usd !== undefined) {
    patch.daily_budget_usd = Math.max(0, Math.min(20, Number(body.daily_budget_usd)));
  }
  if (body.posts_per_day !== undefined) {
    patch.posts_per_day = Math.max(0, Math.min(10, parseInt(body.posts_per_day) || 1));
  }
  if (body.name) patch.name = String(body.name).slice(0, 80);
  if (body.handle) patch.handle = String(body.handle).replace(/^@/, "").slice(0, 60);
  if (body.config && typeof body.config === "object") patch.config = body.config;

  // If resuming and account was paused:
  //  - put back to needs_setup or ready
  //  - CLEAR any stuck rejected/failed board items from previous run so they
  //    don't look like "new rejections" (fixes the "stop work rejected all ideas" bug)
  if (body.paused === false) {
    const { data: existing } = await admin.from("account_documents")
      .select("doc_type").eq("account_id", params.aid).limit(5);
    const hasAll5 = (existing || []).length >= 5;
    patch.status = hasAll5 ? "ready" : "needs_setup";
    // Remove board_items from a prior run that were stuck in a failed/rejected/drafted
    // state so the fresh v5 run starts clean:
    try {
      await admin.from("board_items")
        .delete()
        .eq("account_id", params.aid)
        .in("status", ["rejected","failed"]);
      // Reset in-progress items back to idea so they can be reconsidered fresh
      await admin.from("board_items")
        .update({ status: "idea" })
        .eq("account_id", params.aid)
        .in("status", ["drafted","approved","scheduled"]);
      // Also clear stuck jobs for this account
      await admin.from("jobs")
        .update({ status: "failed", error: "cancelled by account resume" })
        .eq("account_id", params.aid)
        .in("status", ["queued","claimed","in_progress","blocked"]);
    } catch (e) {
      // Non-fatal — tables may not exist on older deploys
    }
  }

  // If PAUSING: don't reject existing ideas (fixes the "stop work rejected everything" bug).
  // Instead leave items in place — the worker simply skips them while paused.
  if (body.paused === true) {
    // Only cancel in-flight jobs; leave board_items as-is so they resume later.
    try {
      await admin.from("jobs")
        .update({ status: "blocked", error: "account paused" })
        .eq("account_id", params.aid)
        .in("status", ["queued","claimed","in_progress"]);
    } catch {}
  }

  const { data, error } = await admin.from("project_accounts")
    .update(patch).eq("id", params.aid).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ account: data });
}

// DELETE — remove account
export async function DELETE(_req: Request, { params }: Ctx) {
  const v = await verifyOwnership(params.pid, params.aid);
  if ("error" in v) return NextResponse.json({ error: v.error }, { status: v.status });
  await supabaseAdmin().from("project_accounts").delete().eq("id", params.aid);
  return NextResponse.json({ ok: true });
}

// PUT /api/projects/[pid]/accounts/[aid] — edit a brand document (v5.7)
export async function PUT(req: Request, { params }: Ctx) {
  const v = await verifyOwnership(params.pid, params.aid);
  if ("error" in v) return NextResponse.json({ error: v.error }, { status: v.status });
  const { admin } = v;
  const body = await req.json().catch(() => ({}));
  const docType = String(body.doc_type || "");
  const content = String(body.content ?? "");
  if (!docType) return NextResponse.json({ error: "doc_type required" }, { status: 400 });
  if (content.length > 200_000) return NextResponse.json({ error: "content too large" }, { status: 400 });
  const { data: cur } = await admin.from("account_documents")
    .select("id,version").eq("account_id", params.aid).eq("doc_type", docType).maybeSingle();
  if (cur) {
    const { error } = await admin.from("account_documents")
      .update({ content, version: (cur.version || 1) + 1, agent: "human_edit", updated_at: new Date().toISOString() })
      .eq("id", cur.id);
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, version: (cur.version || 1) + 1 });
  }
  const { error } = await admin.from("account_documents")
    .insert({ account_id: params.aid, doc_type: docType, content, agent: "human_edit", version: 1 });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true, version: 1 });
}
