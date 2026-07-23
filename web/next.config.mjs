/** @type {import('next').NextConfig} */
export default {
  eslint: { ignoreDuringBuilds: true },
  // v5.10.6 REQ-MCP-OAUTH: Next's App Router will not route a folder whose name
  // begins with a dot, so the RFC well-known documents are served from
  // /api/oauth/metadata and mapped here. Claude's connector fetches these to
  // discover the authorization server before Dynamic Client Registration.
  async rewrites() {
    return [
      { source: "/.well-known/oauth-authorization-server",
        destination: "/api/oauth/metadata" },
      { source: "/.well-known/oauth-authorization-server/api/mcp",
        destination: "/api/oauth/metadata" },
      { source: "/.well-known/oauth-protected-resource",
        destination: "/api/oauth/metadata?type=resource" },
      { source: "/.well-known/oauth-protected-resource/api/mcp",
        destination: "/api/oauth/metadata?type=resource" },
    ];
  },
};
