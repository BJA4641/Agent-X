"use client";
import { useEffect, useState } from "react";

type Conn = { id: string; provider: string; label: string; last_used_at: string | null; created_at: string; scopes: string[] };

export default function McpPanel() {
  const [conns, setConns] = useState<Conn[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState("");
  const [newToken, setNewToken] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    const r = await fetch("/api/mcp/tokens", { cache: "no-store" });
    const j = await r.json();
    setConns(j.connections || []);
    setLoading(false);
  }
  useEffect(() => { refresh(); }, []);

  async function create(provider: string, label: string) {
    const r = await fetch("/api/mcp/tokens", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, label })
    });
    const j = await r.json();
    if (j.token) setNewToken(j.token);
    refresh();
  }

  async function revoke(id: string) {
    await fetch("/api/mcp/tokens?id=" + encodeURIComponent(id), { method: "DELETE" });
    refresh();
  }

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text);
    setCopied(key); setTimeout(() => setCopied(""), 1500);
  }

  const siteUrl = typeof window !== "undefined" ? window.location.origin : "https://your-site.com";
  const exampleToken = newToken || "YOUR_TOKEN";
  const claudeConfig = {
    mcpServers: {
      "agent-x": {
        url: siteUrl + "/api/mcp",
        headers: { Authorization: "Bearer " + exampleToken }
      }
    }
  };
  const claudeConfigStr = JSON.stringify(claudeConfig, null, 2);

  return (
    <div>
      <h2 style={{ marginTop: 36 }}>Connect Claude / ChatGPT / Cursor (MCP)</h2>
      <p className="note" style={{ maxWidth: 720, marginBottom: 12 }}>
        MCP is an open protocol that lets AI tools talk to websites. Generate a token below,
        paste it into Claude Desktop / Cursor / ChatGPT, then chat with Claude and tell it to
        queue Reels, approve drafts, check your wallet, or pause agents — all from inside Claude.
      </p>

      {newToken && (
        <div className="card" style={{ border: "1px solid var(--approved)", background: "rgba(16,185,129,0.08)" }}>
          <b>✅ New token created — copy it now, it won't be shown again:</b>
          <pre style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: 10, marginTop: 8, overflowX: "auto", fontSize: 12 }}>{newToken}</pre>
          <button onClick={() => copy(newToken, "new")}>{copied === "new" ? "Copied!" : "Copy token"}</button>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "16px 0" }}>
        {[
          { p: "claude",  l: "Claude Desktop" },
          { p: "chatgpt", l: "ChatGPT" },
          { p: "cursor",   l: "Cursor IDE" },
          { p: "custom",   l: "Custom / other MCP client" },
        ].map(b => (
          <button key={b.p} onClick={() => create(b.p, b.l)} style={{ fontSize: 13 }}>+ {b.l}</button>
        ))}
      </div>

      {loading ? <p className="note">Loading…</p> : conns.length === 0 ? (
        <p className="note">No MCP connections yet. Create one above.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {conns.map(c => (
            <div key={c.id} className="card" style={{ margin: 0, display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <b>{c.label || c.provider}</b>
                <span className="note" style={{ marginLeft: 8 }}>· {c.provider}</span>
                <div className="note" style={{ fontSize: 12 }}>
                  created {new Date(c.created_at).toLocaleString()}
                  {c.last_used_at && <> · last used {new Date(c.last_used_at).toLocaleString()}</>}
                </div>
              </div>
              <button onClick={() => revoke(c.id)} style={{ background: "var(--failed)", border: "none" }}>Revoke</button>
            </div>
          ))}
        </div>
      )}

      <h3 style={{ marginTop: 28 }}>Setup for Claude Desktop</h3>
      <ol style={{ fontSize: 13, lineHeight: 1.7, maxWidth: 720 }}>
        <li>Generate a token above (choose "Claude Desktop").</li>
        <li>Open Claude Desktop → Settings → Developer → Edit Config.</li>
        <li>Paste this into <code className="mono">claude_desktop_config.json</code>:</li>
      </ol>
      <div style={{ position: "relative" }}>
        <pre style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: 12, fontSize: 12, overflowX: "auto" }}>{claudeConfigStr}</pre>
        <button onClick={() => copy(claudeConfigStr, "cfg")} style={{ position: "absolute", top: 8, right: 8, fontSize: 11, padding: "4px 10px" }}>
          {copied === "cfg" ? "Copied!" : "Copy"}
        </button>
      </div>
      <p className="note" style={{ fontSize: 12, marginTop: 6 }}>Restart Claude Desktop. You will see <b>agent-x</b> under 🔌 Connected tools. Try "Queue a Reel about X".</p>

      <h3 style={{ marginTop: 24 }}>Tools exposed to Claude</h3>
      <ul style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 720 }}>
        <li><b>agentx.queue_topic</b> — queue a new Reel/Short</li>
        <li><b>agentx.list_drafts / approve_draft / reject_draft</b> — manage your approval queue</li>
        <li><b>agentx.list_feed</b> — latest agent activity</li>
        <li><b>agentx.wallet_status</b> — check balance/spend</li>
        <li><b>agentx.projects_list</b> — your active niches</li>
        <li><b>agentx.kill_switch</b> — pause / resume agents</li>
        <li><b>agentx.trends</b> — trending content in your niche</li>
      </ul>
    </div>
  );
}
