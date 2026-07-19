import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const TENANT = process.env.PIPELINE_TENANT_ID || "me";

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const body = await req.json();
  const action = String(body.action || "");
  const admin = supabaseAdmin();

  // ---- any logged-in user: queue a topic for the agents ----
  if (action === "queue_topic") {
    const topic = String(body.topic || "").trim().slice(0, 200);
    if (topic.length < 8) return NextResponse.json({ error: "Topic too short" }, { status: 400 });
    const projectId = cookies().get("ax_project")?.value || null; // v1.6: file under selected project
    const payload: any = { bucket: "user", source: String(body.source || "studio").slice(0, 300), queued_by: user.id };
    if (projectId) payload.project_id = projectId;
    const { error } = await admin.from("board_items")
      .insert({ tenant_id: TENANT, topic, status: "idea", payload });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true });
  }

  // ---- everything below is admin-only ----
  if (!isAdmin(user.email)) return NextResponse.json({ error: "Admin only" }, { status: 403 });

  if (action === "pick_hook") {
    const { id, hook } = body;
    const { data: item } = await admin.from("board_items").select("payload").eq("id", id).single();
    if (!item) return NextResponse.json({ error: "Not found" }, { status: 404 });
    const payload = { ...(item.payload || {}), script: { ...(item.payload?.script || {}), hook: String(hook) } };
    const { error } = await admin.from("board_items").update({ payload }).eq("id", id);
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true });
  }

  if (action === "approve" || action === "reject") {
    const status = action === "approve" ? "approved" : "rejected";
    const { error } = await admin.from("board_items").update({ status }).eq("id", String(body.id)).eq("status", "drafted");
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, status });
  }

  if (action === "retry_failed") {
    // v1.6: one click sends a failed item back to the idea queue. Attempts and
    // error are cleared; a cached script survives so the writer isn't re-billed.
    const { data: item } = await admin.from("board_items").select("payload").eq("id", String(body.id)).eq("status", "failed").single();
    if (!item) return NextResponse.json({ error: "Not a failed item" }, { status: 404 });
    const payload = { ...(item.payload || {}) };
    delete payload.attempts; delete payload.error;
    const { error } = await admin.from("board_items")
      .update({ status: "idea", payload }).eq("id", String(body.id));
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true });
  }

  if (action === "kill_on" || action === "kill_off") {
    const { error } = await admin.from("agent_settings").upsert(
      { tenant_id: TENANT, key: "kill_switch", value: { on: action === "kill_on" } },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, kill: action === "kill_on" });
  }

  if (action === "set_budget") {
    const usd = Number(body.usd);
    if (!(usd >= 0 && usd <= 100)) return NextResponse.json({ error: "0–100 USD" }, { status: 400 });
    const { error } = await admin.from("agent_settings").upsert(
      { tenant_id: TENANT, key: "daily_budget", value: { usd } }, { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, usd });
  }

  if (action === "set_model") {
    const provider = String(body.provider || "");
    if (!["anthropic", "gemini", "openrouter", "groq"].includes(provider))
      return NextResponse.json({ error: "Unknown provider" }, { status: 400 });
    const { error } = await admin.from("agent_settings").upsert(
      { tenant_id: TENANT, key: "llm_provider", value: { provider } }, { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, provider });
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
