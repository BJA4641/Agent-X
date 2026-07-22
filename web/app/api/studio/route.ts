import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const TENANT = process.env.TENANT_ID || "me";

export async function POST(req: Request) {
  const sbServer = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sbServer.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const body = await req.json();
  const { action, itemId, reason, hookIndex } = body;
  const adminUser = isAdmin(user.email);

  // queue_topic is allowed for ANY logged-in user (used from workspace order box, clone page, trends)
  if (action === "queue_topic") {
    const { topic, source } = body;
    if (!topic) return NextResponse.json({ error: "topic required" }, { status: 400 });
    const { error } = await admin.from("board_items").insert({
      tenant_id: TENANT, status: "idea", topic: String(topic).slice(0, 200),
      payload: {
        bucket: source === "trends-desk" ? "proven" : "user",
        source: source || "workspace",
        queued_by: user.id,
      },
    });
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true });
  }

  if (!adminUser) return NextResponse.json({ error: "Admins only." }, { status: 403 });
  const sb = admin;

  if (action === "pick_hook") {
    const { data: cur } = await sb.from("board_items").select("payload").eq("id", itemId).single();
    const payload = { ...(cur?.payload || {}) };
    const opts = payload?.script?.hook_options || [];
    if (typeof hookIndex === "number" && opts[hookIndex]) {
      payload.script = { ...payload.script, hook: opts[hookIndex] };
      payload.hook_choice = { index: hookIndex, at: new Date().toISOString() };
      const { error } = await sb.from("board_items").update({ payload, updated_at: new Date().toISOString() }).eq("id", itemId);
      if (error) return NextResponse.json({ error: error.message }, { status: 400 });
      return NextResponse.json({ ok: true, hook: opts[hookIndex] });
    }
    return NextResponse.json({ error: "bad hook index" }, { status: 400 });
  }
  if (action === "approve" || action === "reject") {
    const status = action === "approve" ? "approved" : "rejected";
    const { data: cur } = await sb.from("board_items").select("payload").eq("id", itemId).single();
    const payload = { ...(cur?.payload || {}) };
    if (action === "reject") payload.rejection = { reason: reason || "not specified", at: new Date().toISOString() };
    const { error } = await sb.from("board_items").update({ status, payload, updated_at: new Date().toISOString() })
      .eq("id", itemId).eq("status", "drafted");
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, status });
  }
  if (action === "soft_pause_on" || action === "soft_pause_off") {
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "soft_pause", value: { on: action === "soft_pause_on" }, updated_at: new Date().toISOString() },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, soft: action === "soft_pause_on" });
  }
  if (action === "kill_on" || action === "kill_off") {
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "kill_switch", value: { on: action === "kill_on" }, updated_at: new Date().toISOString() },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, kill: action === "kill_on" });
  }
  if (action === "set_budget") {
    const usd = Number(body.usd);
    if (!isFinite(usd) || usd < 0 || usd > 100)
      return NextResponse.json({ error: "Budget must be between $0 and $100/day." }, { status: 400 });
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "daily_budget", value: { usd }, updated_at: new Date().toISOString() },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, usd });
  }
  if (action === "set_model") {
    const provider = String(body.provider || "");
    if (!["anthropic", "gemini", "openrouter", "groq"].includes(provider))
      return NextResponse.json({ error: "Unknown provider." }, { status: 400 });
    const model = String(body.model || "").slice(0, 80);
    const auto_fallback = body.auto_fallback !== false; // default true
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "model", value: { provider, model, auto_fallback }, updated_at: new Date().toISOString() },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, provider, model, auto_fallback });
  }
  if (action === "set_autofallback") {
    const on = body.on !== false;
    // Read current model row to preserve provider/model
    const { data: cur } = await sb.from("settings").select("value").eq("tenant_id", TENANT).eq("key", "model").maybeSingle();
    const existing = (cur?.value as any) || { provider: "anthropic" };
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "model", value: { ...existing, auto_fallback: on }, updated_at: new Date().toISOString() },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, auto_fallback: on });
  }
  return NextResponse.json({ error: "Unknown action." }, { status: 400 });
}
