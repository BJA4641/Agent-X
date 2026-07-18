"use client";
/**
 * ChannelConnections — drop-in replacement.
 * Handles: loading state, error state (table/route not yet live), connect/reconnect/disconnect.
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
  blurb: string;
};

type Resp = { platforms: Record<Platform, PlatformStatus>; error?: string };

const FIELD_LABELS: Record<string, string> = {
  accessToken: "Access Token",
  refreshToken: "Refresh Token",
  userId: "Account / Channel ID",
  apiKey: "API Key",
  apiSecret: "API Secret",
  displayName: "Display name (optional)",
};

export default function ChannelConnections() {
  const [data, setData] = useState<Resp | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<Platform | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string>("");

  useEffect(() => { void refresh(); }, []);

  async function refresh() {
    setLoadErr(null);
    try {
      const r = await fetch("/api/connections", { cache: "no-store" });
      if (r.status === 404) {
        setLoadErr("Connections API not deployed yet. Run the SQL setup first (see docs).");
        setData(null);
        return;
      }
      if (!r.ok) {
        const t = await r.text().catch(() => "");
        setLoadErr(`Could not load connections (${r.status}): ${t.slice(0, 180)}`);
        setData(null);
        return;
      }
      const j = await r.json();
      if (j.error) { setLoadErr(j.error); setData(null); return; }
      setData(j);
    } catch (e: any) {
      setLoadErr("Network error loading connections.");
    }
  }

  async function save(p: Platform) {
    setBusy(p); setMsg("");
    const credentials: Record<string, string> = {};
    Object.entries(form).forEach(([k, v]) => { if (v.trim()) credentials[k] = v.trim(); });
    const r = await fetch("/api/connections", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform: p, credentials, display_name: form.displayName || null }),
    });
    const j = await r.json().catch(() => ({}));
    setBusy(null);
    if (!r.ok) { setMsg(`Error: ${j.error || r.statusText}`); return; }
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
    else setMsg("Disconnect failed.");
  }

  if (loadErr) {
    return (
      <div className="card" style={{ borderLeft: "3px solid #e5484d" }}>
        <h3>Connections not available yet</h3>
        <p className="note" style={{ fontSize: 13 }}>{loadErr}</p>
        <p className="note" style={{ fontSize: 13, marginTop: 8 }}>
          Run <code className="mono">db/setup_v1.4.sql</code> in Supabase → SQL editor, then refresh.
        </p>
      </div>
    );
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
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <h3 style={{ margin: 0 }}>{s.label}</h3>
                <span className="tag" style={{
                  marginLeft: "auto",
                  color: s.connected ? "var(--published)" : "var(--dim)",
                }}>{s.connected ? "● connected" : "○ not connected"}</span>
              </div>
              <p className="note" style={{ marginTop: 8, fontSize: 13 }}>{s.blurb}</p>

              {s.connected && !isEditing && (
                <>
                  {s.display_name && <p className="mono" style={{ fontSize: 12, margin: "6px 0" }}>{s.display_name}</p>}
                  {s.last_test_at && <p className="note" style={{ fontSize: 12 }}>Last verified {new Date(s.last_test_at).toLocaleString()}</p>}
                  {s.error && <p style={{ color: "#e5484d", fontSize: 12 }}>{s.error}</p>}
                  <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                    <button className="ghost" onClick={() => { setEditing(p); setForm({}); }}>Reconnect</button>
                    <button className="ghost" onClick={() => revoke(p)} disabled={busy === p}>Disconnect</button>
                  </div>
                </>
              )}

              {!s.connected && !isEditing && (
                <>
                  <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                    <button onClick={() => setEditing(p)}>Connect</button>
                    <a className="ghost" style={{ padding: "6px 12px", border: "1px solid var(--line)", borderRadius: 8, fontSize: 13, textDecoration: "none" }}
                       href={s.docUrl} target="_blank" rel="noreferrer">How to get keys ↗</a>
                  </div>
                </>
              )}

              {isEditing && (
                <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
                  {["displayName", ...s.required].map((k) => (
                    <div key={k}>
                      <label className="note" style={{ fontSize: 12 }}>{FIELD_LABELS[k] || k}</label>
                      <input
                        className="mono"
                        type={k.toLowerCase().includes("token") || k.toLowerCase().includes("secret") || k.toLowerCase().includes("key") ? "password" : "text"}
                        autoComplete="off"
                        placeholder={k}
                        value={form[k] || ""}
                        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                        style={{ width: "100%", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px", color: "inherit", fontFamily: "var(--font-mono)", fontSize: 12 }}
                      />
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
        Tokens are encrypted at rest using AES-256. The browser never sees them after save.
        The worker decrypts them server-side only when publishing.
      </p>
    </>
  );
}
