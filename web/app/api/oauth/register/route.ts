/**
 * RFC 7591 Dynamic Client Registration.
 *
 * Claude calls this with its redirect URIs and gets back a client_id. We issue
 * PUBLIC clients (no secret) because the flow is PKCE-protected — a secret in a
 * desktop/web client is not a secret, and OAuth 2.1 explicitly prefers PKCE.
 */
import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";
import crypto from "crypto";

export const dynamic = "force-dynamic";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
  "Cache-Control": "no-store",
};

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: CORS });
}

export async function POST(req: Request) {
  let body: any = {};
  try { body = await req.json(); } catch { /* empty registration is still valid */ }

  const redirectUris: string[] = Array.isArray(body?.redirect_uris) ? body.redirect_uris : [];
  if (redirectUris.length === 0) {
    return NextResponse.json(
      { error: "invalid_redirect_uri", error_description: "redirect_uris is required" },
      { status: 400, headers: CORS });
  }
  // Only https (or localhost for desktop clients) may receive an auth code.
  for (const uri of redirectUris) {
    try {
      const u = new URL(uri);
      const localhost = u.hostname === "localhost" || u.hostname === "127.0.0.1";
      if (u.protocol !== "https:" && !localhost) {
        return NextResponse.json(
          { error: "invalid_redirect_uri", error_description: `insecure redirect_uri: ${uri}` },
          { status: 400, headers: CORS });
      }
    } catch {
      return NextResponse.json(
        { error: "invalid_redirect_uri", error_description: `malformed redirect_uri: ${uri}` },
        { status: 400, headers: CORS });
    }
  }

  const clientId = "axc_" + crypto.randomBytes(16).toString("hex");
  const row = {
    client_id: clientId,
    client_secret: null as string | null,
    client_name: String(body?.client_name || "MCP client").slice(0, 120),
    redirect_uris: redirectUris,
    grant_types: ["authorization_code", "refresh_token"],
    token_endpoint_auth_method: "none",
  };

  const { error } = await supabaseAdmin().from("oauth_clients").insert(row);
  if (error) {
    return NextResponse.json(
      { error: "server_error", error_description: error.message },
      { status: 500, headers: CORS });
  }

  return NextResponse.json({
    client_id: clientId,
    client_id_issued_at: Math.floor(Date.now() / 1000),
    client_name: row.client_name,
    redirect_uris: redirectUris,
    grant_types: row.grant_types,
    response_types: ["code"],
    token_endpoint_auth_method: "none",
  }, { status: 201, headers: CORS });
}
