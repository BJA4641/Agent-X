import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

// v5.11.23 REQ-ACCOUNT-PIPELINE (DEC-076)
// The account page's "Posts" tab read `account_posts` (the legacy kickoff
// planner table) while the real pipeline writes to `board_items` — so an
// account with a fully-rendered approved carousel showed "No posts yet".
// This endpoint is the account-scoped view of the ACTUAL pipeline: the same
// rows Studio shows, filtered to one account, with the same approve/reject
// transition Studio uses (drafted → approved|rejected, CAS-guarded).

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

export async function GET(_req: Request, { params }: Ctx) {
  const v = await verifyOwnership(params.pid, params.aid);
  if ("error" in v) return NextResponse.json({ ok: false, error: v.error }, { status: v.status });
  const { admin } = v;

  const { data, error } = await admin.from("board_items")
    .select("id,topic,status,created_at,payload")
    .eq("account_id", params.aid)
    .in("status", ["idea", "prep", "drafted", "approved", "scheduled", "published", "quarantined"])
    .order("created_at", { ascending: false })
    .limit(60);
  if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 500 });

  // Slim the payload — the raw column carries scripts, receipts and audit
  // trails the card doesn't need; ship only what renders.
  const items = (data || []).map((r: any) => {
    const p = r.payload || {};
    const script = p.carousel_script || p.script || {};
    return {
      id: r.id,
      topic: r.topic,
      status: r.status,
      created_at: r.created_at,
      format: p.format || (String(r.topic || "").startsWith("[carousel]") ? "carousel" : "reel"),
      images: Array.isArray(p.carousel_urls) ? p.carousel_urls.slice(0, 6) : [],
      video_url: p.video_url || p.final_video_url || null,
      caption: p.caption || script.caption || "",
      hook: (Array.isArray(script.slides) && script.slides[0]?.heading) || script.hook || "",
      dry_run_only: !!p.dry_run_only,
    };
  });
  return NextResponse.json({ ok: true, items });
}

export async function POST(req: Request, { params }: Ctx) {
  const v = await verifyOwnership(params.pid, params.aid);
  if ("error" in v) return NextResponse.json({ ok: false, error: v.error }, { status: v.status });
  const { admin } = v;
  const body = await req.json().catch(() => ({}));
  const { action, itemId, reason } = body;

  if (action !== "approve" && action !== "reject")
    return NextResponse.json({ ok: false, error: "unknown action" }, { status: 400 });
  if (!itemId) return NextResponse.json({ ok: false, error: "itemId required" }, { status: 400 });

  // Belt-and-braces: the item must belong to THIS account (ownership of the
  // account was already verified above — this stops cross-account itemIds).
  const { data: cur } = await admin.from("board_items")
    .select("id,account_id,status,payload").eq("id", itemId).single();
  if (!cur || String(cur.account_id) !== String(params.aid))
    return NextResponse.json({ ok: false, error: "item not in this account" }, { status: 404 });

  const status = action === "approve" ? "approved" : "rejected";
  const payload = { ...(cur.payload || {}) };
  if (action === "reject")
    payload.rejection = { reason: reason || "not specified", by: "owner", at: new Date().toISOString() };
  else
    payload.approved_by = { by: "owner", at: new Date().toISOString() };

  // Same CAS guard as Studio: only a drafted item can transition — a double
  // click or a stale tab loses the race loudly instead of flip-flopping state.
  const { error, data: upd } = await admin.from("board_items")
    .update({ status, payload, updated_at: new Date().toISOString() })
    .eq("id", itemId).eq("status", "drafted").select("id");
  if (error) return NextResponse.json({ ok: false, error: error.message }, { status: 400 });
  if (!upd?.length)
    return NextResponse.json({ ok: false, error: "item is no longer in drafted state" }, { status: 409 });
  return NextResponse.json({ ok: true, status });
}
