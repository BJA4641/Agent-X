/**
 * OAuth discovery metadata for the Agent-X MCP server.
 *
 * Claude.ai's "Add custom connector" dialog has no header field — it expects the
 * MCP server to be an OAuth 2.1 protected resource. When no Client ID is given
 * it attempts Dynamic Client Registration, which starts by fetching
 * /.well-known/oauth-authorization-server. Without these documents the dialog
 * fails with "Couldn't register with <server>'s sign-in service".
 *
 * Served from /api/oauth/metadata and mapped to both well-known paths by
 * rewrites in next.config.mjs (Next's App Router will not route a folder whose
 * name begins with a dot).
 */
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function baseUrl(req: Request) {
  const env = process.env.NEXT_PUBLIC_SITE_URL || process.env.SITE_URL;
  if (env) return env.replace(/\/$/, "");
  const u = new URL(req.url);
  return `${u.protocol}//${u.host}`;
}

export async function GET(req: Request) {
  const base = baseUrl(req);
  const type = new URL(req.url).searchParams.get("type");

  // RFC 9728 — protected resource metadata
  if (type === "resource") {
    return NextResponse.json({
      resource: `${base}/api/mcp`,
      authorization_servers: [base],
      scopes_supported: ["mcp"],
      bearer_methods_supported: ["header"],
    }, { headers: cors() });
  }

  // RFC 8414 — authorization server metadata
  return NextResponse.json({
    issuer: base,
    authorization_endpoint: `${base}/api/oauth/authorize`,
    token_endpoint: `${base}/api/oauth/token`,
    registration_endpoint: `${base}/api/oauth/register`,
    scopes_supported: ["mcp"],
    response_types_supported: ["code"],
    grant_types_supported: ["authorization_code", "refresh_token"],
    code_challenge_methods_supported: ["S256"],          // PKCE is mandatory in 2.1
    token_endpoint_auth_methods_supported: ["none", "client_secret_post"],
  }, { headers: cors() });
}

export function OPTIONS() {
  return new NextResponse(null, { status: 204, headers: cors() });
}

function cors(): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Cache-Control": "no-store",
  };
}
