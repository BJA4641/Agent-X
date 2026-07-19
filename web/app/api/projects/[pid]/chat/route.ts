/**
 * POST /api/projects/[pid]/chat — project-level chat (founder notes applied to ALL accounts in the project)
 *   { content }
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export async function POST(req: Request, { params }: { params: { pid: string } }) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  const { pid } = params;
  const { data: proj } = await supabaseAdmin().from("projects")
    .select("user_id").eq("id", pid).single();
  if (!proj || proj.user_id !== user.id) return NextResponse.json({ error: "not found" }, { status: 404 });
  const body = await req.json().catch(() => ({}));
  const content = String(body.content || "").trim();
  if (!content) return NextResponse.json({ error: "content required" }, { status: 400 });
  const { data, error } = await supabaseAdmin().from("memory_entries").insert({
    project_id: pid, role: "user", content: content.slice(0, 2000),
    metadata: { from: "project_console" },
  }).select().single();
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ entry: data });
}
