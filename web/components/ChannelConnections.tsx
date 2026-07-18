"use client";
/**
 * ChannelConnections — drop into web/app/dashboard/settings/page.tsx
 * replacing the static "Channel connections" cards.
 *
 * Usage in settings/page.tsx:
 *   import ChannelConnections from "@/components/ChannelConnections";
 *   ...
 *   <h2 style={{ marginTop: 28 }}>Channel connections</h2>
 *   <ChannelConnections />
 */
import { useEffect, useState } from "react";

type Platform = "instagram" | "youtube" | "tiktok" | "x" | "linkedin" | "pinterest" | "facebook";

type PlatformStatus = {
  label: string;
  connected: boolean;
  display_name: string | null;
  last_test_at: string | null;
  error: string | null;
  required: string[];
  oauth: boolean;
  docUrl: string;
};

type Resp = { platforms: Record<Platform, PlatformStatus> };

const FIELD_LABELS: Record<string, string> = {
  accessToken: "Access Token",
  refreshToken: "Refresh Token",
  userId: "Account / Channel ID",
  apiKey: "API Key",
  apiSecret: "API Secret",
  expiresAt: "Expires At (ISO)",
};

export default function ChannelConnections() {
  const [data, setData] = useState<Resp | null>(null);
  const [editing, setEditing] = useState<Platform | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string>("");

  useEffect(() => { void refresh(); }, []);

  async function refresh() {
    const r = await fetch("/api/connections");
    if (r.ok) setData(await r.json());
  }

  async function save(p: Platform) {
    setBusy(p); setMsg("");
    // Convert platform-specific form keys into the Creds object
    const creds: Record<string, string> = {};
    Object.entries(form).forEach(([k, v]) => { if (v.trim()) creds[k] = v.trim(); });
    const r = await fetch("/api/connections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: p, credentials: creds, display_name: form._displayName || null }),
    });
    const j = await r.json();
    setBusy(null);
    if (!r.ok) { setMsg(`Error: ${j.error}`); return; }
    setEditing(null); setForm({}); setMsg(`${data?.platforms[p]?.label || p} connected ✓`);
    await refresh();
  }

  async function revoke(p: Platform) {
    if (!confirm(`Disconnect ${data?.platforms[p]?.label || p}?`)) return;
    setBusy(p);
    const r = await fetch("/api/connections", {
      method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: p }),
    });
    setBusy(null);
    if (r.ok) { setMsg("Disconnected."); await refresh(); }
  }

  if (!data) return <p className="note">Loading connections…</p>;

  return (
    <>
      <div className="grid">
        {(Object.keys(data.platforms) as Platform[]).map((p) => {
          const s = data.platforms[p];
          const isEditing = editing === p;
          return (
            <div className="card" key={p}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <h3 style={{ margin: 0 }}>{s.label}</h3>
                <span className="tag" style={{
                  marginLeft: "auto",
                  color: s.connected ? "var(--published)" : "var(--dim)",
                }}>{s.connected ? "● connected" : "○ not connected"}</span>
              </div>

              {s.connected && !isEditing && (
                <>
                  {s.display_name && <p className="mono" style={{ fontSize: 12, margin: "6px 0" }}>{s.display_name}</p>}
                  {s.last_test_at && <p className="note" style={{ fontSize: 12 }}>Last verified {new Date(s.last_test_at).toLocaleString()}</p>}
                  {s.error && <p style={{ color: "#e5484d", fontSize: 12 }}>{s.error}</p>}
                  <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                    <button className="ghost" onClick={() => { setEditing(p); setForm({}); }}>Reconnect</button>
                    <button className="ghost" onClick={() => revoke(p)} disabled={busy === p}>Disconnect</button>
                  </div>
                </>
              )}

              {!s.connected && !isEditing && (
                <>
                  <p className="note" style={{ marginTop: 8, fontSize: 13 }}>
                    {s.oauth ? "Connect to enable auto-publishing. Tokens are encrypted at rest." : "Paste your API key below."}
                  </p>
                  <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                    <button onClick={() => setEditing(p)}>Connect</button>
                    <a className="ghost" style={{ padding: "6px 12px", border: "1px solid var(--line)", borderRadius: 8, fontSize: 13, textDecoration: "none" }}
                       href={s.docUrl} target="_blank" rel="noreferrer">How to get keys ↗</a>
                  </div>
                </>
              )}

              {isEditing && (
                <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
                  <label className="note" style={{ fontSize: 12 }}>Display name (optional)</label>
                  <input className="mono" placeholder="@yourhandle" value={form._displayName || ""}
                         onChange={(e) => setForm({ ...form, _displayName: e.target.value })}
                         style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px", color: "inherit" }} />
                  {s.required.map((k) => (
                    <div key={k}>
                      <label className="note" style={{ fontSize: 12 }}>{FIELD_LABELS[k] || k}</label>
                      <input className="mono" type="password" autoComplete="off"
                             placeholder={k} value={form[k] || ""}
                             onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                             style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px", color: "inherit", fontFamily: "var(--font-mono)", fontSize: 12 }} />
                    </div>
                  ))}
                  <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                    <button onClick={() => save(p)} disabled={busy === p}>
                      {busy === p ? "Saving…" : (s.connected ? "Update" : "Connect")}
                    </button>
                    <button className="ghost" onClick={() => { setEditing(null); setForm({}); }}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {msg && <p className="note" style={{ marginTop: 10 }}>{msg}</p>}

      <p className="note" style={{ marginTop: 16, fontSize: 12 }}>
        Tokens are encrypted in the database using AES (via Postgres <code className="mono">pgcrypto</code>).
        The web client never receives them. Add OAuth "Connect with Instagram/Google/TikTok" buttons
        by extending this component with each platform's OAuth redirect URI.
      </p>
    </>
  );
}
