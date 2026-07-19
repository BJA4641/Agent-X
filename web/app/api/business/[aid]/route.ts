import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

/**
 * GET /api/business/[aid]
 * Returns the full brand bible (all 13 docs) + account metadata for any account
 * the current user owns. v5.3 — addresses "where are the business plans" /
 * "brand tone identical to brand identity" / "business/brand/tone access for all projects".
 */
type Ctx = { params: { aid: string } };

export async function GET(_req: Request, { params }: Ctx) {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });

  // Fetch the account + verify ownership
  const { data: acc } = await admin
    .from("project_accounts")
    .select("id,name,handle,niche,project_id,paused,posts_per_day,daily_budget_usd,projects:project_id(user_id,name)")
    .eq("id", params.aid).single();
  if (!acc) return NextResponse.json({ error: "not found" }, { status: 404 });
  const projectUser = (acc as any).projects?.user_id;
  // Allow admin (jadaridi8@gmail.com) OR project owner
  const isAdmin = user.email && ["jadaridi8@gmail.com"].includes(user.email.toLowerCase());
  if (!isAdmin && projectUser !== user.id) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }

  // Fetch all brand docs
  const { data: docs } = await admin
    .from("account_documents")
    .select("doc_type,content,updated_at")
    .eq("account_id", params.aid)
    .order("doc_type");
  const docMap: Record<string, any> = {};
  for (const d of docs || []) docMap[d.doc_type] = d;

  // Stats
  const [{ data: posts }, { data: grades }] = await Promise.all([
    admin.from("board_items")
      .select("id,status,topic,created_at,payload")
      .eq("account_id", params.aid)
      .order("created_at", { ascending: false })
      .limit(30),
    admin.from("content_grades")
      .select("overall,passed,created_at")
      .order("created_at", { ascending: false })
      .limit(50),
  ]);

  const avgGrade = (grades || []).length
    ? (grades || []).reduce((s: number, g: any) => s + Number(g.overall || 0), 0) / (grades || []).length
    : 0;

  return NextResponse.json({
    account: {
      id: acc.id, name: acc.name, handle: acc.handle, niche: acc.niche,
      paused: acc.paused, posts_per_day: acc.posts_per_day,
      daily_budget_usd: acc.daily_budget_usd,
      project_name: (acc as any).projects?.name,
    },
    documents: docMap,
    posts: (posts || []).map((p: any) => ({
      id: p.id, status: p.status, topic: p.topic, created_at: p.created_at,
      video_url: p.payload?.video_url, script: p.payload?.script,
      grade: p.payload?.grade, captions: p.payload?.captions,
    })),
    stats: {
      posts_count: (posts || []).length,
      published_count: (posts || []).filter((p: any) => p.status === "published").length,
      avg_grade: +avgGrade.toFixed(2),
      docs_count: (docs || []).length,
    },
  });
}
