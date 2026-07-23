import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import fs from "fs";
import path from "path";

const TENANT = process.env.TENANT_ID || "me";

// Load catalog server-side (from repo JSON at build/runtime). We read directly
// from pipeline/agentcore/providers_catalog.json so it's always in sync with
// what the worker can actually call.
function loadCatalog(): any {
  try {
    const p = path.join(process.cwd(), "..", "pipeline", "agentcore", "providers_catalog.json");
    if (!fs.existsSync(p)) {
      // dev / vercel layout (pipeline may be at root of monorepo or sibling)
      const p2 = path.join(process.cwd(), "pipeline", "agentcore", "providers_catalog.json");
      if (fs.existsSync(p2)) return JSON.parse(fs.readFileSync(p2, "utf8"));
      return {};
    }
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return {};
  }
}

function publicCatalog(cat: any) {
  const out: any = {};
  for (const [k, spec] of Object.entries<any>(cat)) {
    if (k.startsWith("_") || !spec || typeof spec !== "object" || !Array.isArray(spec.models)) continue;
    out[k] = {
      label: spec._label || k,
      defaults: spec._default || [],
      default_tier: spec._default_tier || null,
      models: spec.models.map((m: any) => ({
        id: m.id, name: m.name, provider: m.provider,
        paid: !!m.paid, free_tier: !!m.free_tier,
        est_usd: m.est_usd ?? null,
        has_key: !!m.key_env && !!process.env[m.key_env],
        key_env: m.key_env || null,
        arena_rank: m.arena_rank || null,
        best_for: m.best_for || null,
      })),
    };
  }
  return out;
}

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "admins only" }, { status: 403 });
  const admin = supabaseAdmin();
  const keys = ["model","model_t2i","model_ie","model_t2v","model_i2v","model_tts","model_vedit"];
  const { data: rows } = await admin.from("settings").select("key,value").eq("tenant_id", TENANT).in("key", keys);
  const chosen: Record<string, any> = {};
  for (const r of rows || []) chosen[r.key] = r.value;

  // v5.8.7: ground truth from the WORKER process (Railway env), not this one.
  //   provider_status    <- providers.probe : linked / alive / balance / spend
  //   provider_inventory <- boot            : which key names the worker sees
  //   cost_mode          <- costmode        : normal | free_only
  let provider_status: any = null, worker_inventory: any = null, cost_mode: any = null;
  try {
    const { data: extra } = await admin.from("settings").select("key,value")
      .eq("tenant_id", TENANT).in("key", ["provider_status", "provider_inventory", "cost_mode"]);
    for (const r of extra || []) {
      if (r.key === "provider_status") provider_status = r.value;
      if (r.key === "provider_inventory") worker_inventory = r.value;
      if (r.key === "cost_mode") cost_mode = r.value;
    }
  } catch { /* best effort */ }

  return NextResponse.json({
    catalog: publicCatalog(loadCatalog()),
    chosen,
    provider_status, worker_inventory, cost_mode,
    schema_version: chosen.model ? undefined : "needs_sql",
  });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "login" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "admins only" }, { status: 403 });
  const body = await req.json().catch(() => ({}));
  const { category, model_id } = body;
  const keyMap: Record<string, string> = {
    text: "model", text_to_image: "model_t2i", image_edit: "model_ie",
    text_to_video: "model_t2v", image_to_video: "model_i2v",
    voice: "model_tts", video_edit: "model_vedit",
  };
  if (!keyMap[category]) return NextResponse.json({ error: "bad category" }, { status: 400 });
  const admin = supabaseAdmin();
  const value = category === "text"
    ? { provider: (model_id || "").split("-")[0] || "anthropic", model: model_id, auto_fallback: true }
    : { model: model_id };
  const { error } = await admin.from("settings").upsert(
    { tenant_id: TENANT, key: keyMap[category], value, updated_at: new Date().toISOString() },
    { onConflict: "tenant_id,key" });
  if (error) return NextResponse.json({ error: error.message }, { status: 400 });
  return NextResponse.json({ ok: true, category, model_id });
}
