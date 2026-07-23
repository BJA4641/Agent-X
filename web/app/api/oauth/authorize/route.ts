/**
 * Authorization endpoint (RFC 6749 §4.1 + PKCE RFC 7636).
 *
 * GET  — the user must already be signed in to Agent-X in this browser. We show
 *        nothing fancy: verify the client + redirect_uri, mint a short-lived
 *        code bound to (user, client, PKCE challenge), and redirect back.
 * POST — same, for clients that submit a consent form.
 *
 * Security notes:
 *  - redirect_uri must EXACTLY match one registered for the client (no prefix
 *    matching — that is a classic open-redirect / code-theft hole).
 *  - PKCE S256 is required; a code with no challenge cannot be exchanged.
 *  - codes live 5 minutes and are single-use (used_at is set on exchange).
 */
import { NextResponse } from "next/server";
import { supabaseAdmin, supabaseServer } from "@/lib/supabase/server";
import crypto from "crypto";

export const dynamic = "force-dynamic";

const CODE_TTL_MS = 5 * 60 * 1000;

function err(redirect: string | null, code: string, desc: string, state?: string | null) {
  if (redirect) {
    const u = new URL(redirect);
    u.searchParams.set("error", code);
    u.searchParams.set("error_description", desc);
    if (state) u.searchParams.set("state", state);
    return NextResponse.redirect(u.toString());
  }
  return NextResponse.json({ error: code, error_description: desc }, { status: 400 });
}

async function handle(req: Request) {
  const url = new URL(req.url);
  const p = url.searchParams;
  const clientId = p.get("client_id") || "";
  const redirectUri = p.get("redirect_uri") || "";
  const state = p.get("state");
  const challenge = p.get("code_challenge") || "";
  const method = (p.get("code_challenge_method") || "S256").toUpperCase();
  const scope = p.get("scope") || "mcp";

  if (!clientId || !redirectUri) return err(null, "invalid_request", "client_id and redirect_uri are required");
  if (!challenge) return err(null, "invalid_request", "PKCE code_challenge is required");
  if (method !== "S256") return err(null, "invalid_request", "only S256 PKCE is supported");

  const admin = supabaseAdmin();
  const { data: client } = await admin.from("oauth_clients")
    .select("client_id,redirect_uris").eq("client_id", clientId).maybeSingle();
  if (!client) return err(null, "invalid_client", "unknown client_id — register first");

  const allowed: string[] = (client as any).redirect_uris || [];
  if (!allowed.includes(redirectUri)) {
    return err(null, "invalid_request", "redirect_uri does not exactly match a registered URI");
  }

  // The browser session decides WHO is authorising. No session -> send them to
  // login and come back with the identical query string.
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) {
    const back = `/login?next=${encodeURIComponent(url.pathname + url.search)}`;
    return NextResponse.redirect(new URL(back, url.origin).toString());
  }

  const code = "axcode_" + crypto.randomBytes(24).toString("hex");
  const { error } = await admin.from("oauth_codes").insert({
    code, client_id: clientId, user_id: user.id, redirect_uri: redirectUri,
    code_challenge: challenge, code_challenge_method: "S256", scope,
    expires_at: new Date(Date.now() + CODE_TTL_MS).toISOString(),
  });
  if (error) return err(redirectUri, "server_error", error.message, state);

  const out = new URL(redirectUri);
  out.searchParams.set("code", code);
  if (state) out.searchParams.set("state", state);
  return NextResponse.redirect(out.toString());
}

export async function GET(req: Request) { return handle(req); }
export async function POST(req: Request) { return handle(req); }
