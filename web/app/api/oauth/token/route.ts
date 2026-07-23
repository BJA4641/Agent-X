/**
 * Token endpoint — authorization_code (with PKCE verification) and refresh_token.
 *
 * The PKCE check is the part that actually protects a public client: the code
 * is only exchangeable by whoever holds the verifier whose SHA-256 matches the
 * challenge presented at /authorize.
 */
import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";
import crypto from "crypto";

export const dynamic = "force-dynamic";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
  "Cache-Control": "no-store",
};
const ACCESS_TTL_S = 60 * 60 * 24 * 30;   // 30 days

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

function bad(desc: string, code = "invalid_grant", status = 400) {
  return NextResponse.json({ error: code, error_description: desc }, { status, headers: CORS });
}

function b64url(buf: Buffer) {
  return buf.toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function readParams(req: Request): Promise<Record<string, string>> {
  const ct = req.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try { return (await req.json()) || {}; } catch { return {}; }
  }
  const text = await req.text();
  return Object.fromEntries(new URLSearchParams(text).entries());
}

export async function POST(req: Request) {
  const p = await readParams(req);
  const admin = supabaseAdmin();
  const grant = p.grant_type;

  if (grant === "refresh_token") {
    const rt = p.refresh_token;
    if (!rt) return bad("refresh_token is required");
    const { data: tok } = await admin.from("oauth_tokens")
      .select("*").eq("refresh_token", rt).is("revoked_at", null).maybeSingle();
    if (!tok) return bad("unknown or revoked refresh_token");
    const access = "axat_" + crypto.randomBytes(32).toString("hex");
    const refresh = "axrt_" + crypto.randomBytes(32).toString("hex");
    await admin.from("oauth_tokens").update({ revoked_at: new Date().toISOString() })
      .eq("refresh_token", rt);
    await admin.from("oauth_tokens").insert({
      access_token: access, refresh_token: refresh,
      client_id: (tok as any).client_id, user_id: (tok as any).user_id,
      scope: (tok as any).scope || "mcp",
      expires_at: new Date(Date.now() + ACCESS_TTL_S * 1000).toISOString(),
    });
    return NextResponse.json({
      access_token: access, refresh_token: refresh, token_type: "Bearer",
      expires_in: ACCESS_TTL_S, scope: (tok as any).scope || "mcp",
    }, { headers: CORS });
  }

  if (grant !== "authorization_code") {
    return bad("unsupported grant_type", "unsupported_grant_type");
  }

  const code = p.code, verifier = p.code_verifier, redirectUri = p.redirect_uri;
  if (!code || !verifier) return bad("code and code_verifier are required");

  const { data: row } = await admin.from("oauth_codes").select("*").eq("code", code).maybeSingle();
  if (!row) return bad("unknown code");
  const c: any = row;
  if (c.used_at) return bad("code already used");                 // single use
  if (new Date(c.expires_at).getTime() < Date.now()) return bad("code expired");
  if (redirectUri && redirectUri !== c.redirect_uri) return bad("redirect_uri mismatch");
  if (p.client_id && p.client_id !== c.client_id) return bad("client_id mismatch");

  // PKCE: SHA-256(verifier) must equal the stored challenge.
  const computed = b64url(crypto.createHash("sha256").update(verifier).digest());
  if (computed !== c.code_challenge) return bad("PKCE verification failed");

  await admin.from("oauth_codes").update({ used_at: new Date().toISOString() }).eq("code", code);

  const access = "axat_" + crypto.randomBytes(32).toString("hex");
  const refresh = "axrt_" + crypto.randomBytes(32).toString("hex");
  const { error } = await admin.from("oauth_tokens").insert({
    access_token: access, refresh_token: refresh, client_id: c.client_id,
    user_id: c.user_id, scope: c.scope || "mcp",
    expires_at: new Date(Date.now() + ACCESS_TTL_S * 1000).toISOString(),
  });
  if (error) return bad(error.message, "server_error", 500);

  return NextResponse.json({
    access_token: access, refresh_token: refresh, token_type: "Bearer",
    expires_in: ACCESS_TTL_S, scope: c.scope || "mcp",
  }, { headers: CORS });
}
