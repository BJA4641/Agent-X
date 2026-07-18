import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

const TENANT = process.env.TENANT_ID || "me";

export async function POST(req: Request) {
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user || !isAdmin(user.email)) return NextResponse.json({ error: "Admins only." }, { status: 403 });
  const { action, itemId, reason, hookIndex } = await req.json();
  const sb = supabaseAdmin();

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
  if (action === "kill_on" || action === "kill_off") {
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "kill_switch", value: { on: action === "kill_on" }, updated_at: new Date().toISOString() },
      { onConflict: "tenant_id,key" });
    if (error) return NextResponse.json({ error: error.message }, { status: 400 });
    return NextResponse.json({ ok: true, kill: action === "kill_on" });
  }
  return NextResponse.json({ error: "Unknown action." }, { status: 400 });
}
