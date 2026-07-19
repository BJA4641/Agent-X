import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

async function checkOwnership(userId: string, aid: string) {
  const r = await supabaseAdmin().from("project_accounts")
    .select("id,project_id,user_id")
    .eq("id", aid).eq("user_id", userId).single();
  return r.data || null;
}

export async function GET(_: Request, { params }: { params: Promise<{ pid: string; aid: string }> }) {
  const { pid, aid } = await params;
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const acc = await checkOwnership(user.id, aid);
  if (!acc) return NextResponse.json({ error: "not found" }, { status: 404 });

  const [docs, posts] = await Promise.all([
    supabaseAdmin().from("account_documents").select("*")
      .eq("account_id", aid),
    supabaseAdmin().from("account_posts").select("*")
      .eq("account_id", aid).order("created_at", { ascending: false }).limit(50)
  ]);
  return NextResponse.json({
    documents: Object.fromEntries((docs.data||[]).map((d:any) => [d.doc_type, d])),
    posts: posts.data || []
  });
}

export async function DELETE(_: Request, { params }: { params: Promise<{ pid: string; aid: string }> }) {
  const { aid } = await params;
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const acc = await checkOwnership(user.id, aid);
  if (!acc) return NextResponse.json({ error: "not found" }, { status: 404 });
  await supabaseAdmin().from("project_accounts").delete().eq("id", aid);
  return NextResponse.json({ ok: true });
}
