"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Account = {
  id: string; name: string; handle: string; niche: string; platforms: string[];
  status: string; avatar_emoji: string; created_at: string;
  account_posts?: { status: string }[];
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  needs_setup:   { label: "queued", color: "#64748b" },
  architecting:  { label: "architect building brand…", color: "#f59e0b" },
  strategizing:  { label: "strategist planning posts…", color: "#a78bfa" },
  ready:         { label: "ready", color: "#10b981" },
  paused:        { label: "paused", color: "#ef4444" },
};

export default function ProjectDetailPage() {
  const { pid } = useParams<{ pid: string }>();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [name, setName] = useState("");
  const [handle, setHandle] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    const r = await fetch(`/api/projects/${pid}/accounts`, { cache: "no-store" });
    const j = await r.json();
    setAccounts(j.accounts || []);
    setLoading(false);
  }
  useEffect(() => { if (pid) refresh(); }, [pid]);
  useEffect(() => { if (pid) { const id = setInterval(refresh, 8000); return () => clearInterval(id); } }, [pid]);

  async function add() {
    if (!name.trim()) return;
    await fetch(`/api/projects/${pid}/accounts`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), handle: handle.trim() || name.toLowerCase().replace(/\s+/g,"_") }),
    });
    setName(""); setHandle("");
    refresh();
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link href="/dashboard/projects" className="note" style={{ fontSize: 13 }}>← All projects</Link>
      </div>
      <h1>Project accounts</h1>
      <p className="lead">
        Each card below is a separate brand account within this project. The Architect agent writes
        a full business plan, brand kit, tone guide, visual rules, and content rules for each one.
        The Strategist then plans 10 kickoff posts.
      </p>

      {loading ? <p className="note">Loading accounts…</p> : accounts.length === 0 ? (
        <div className="card"><p className="note">No accounts yet. Add one below, or hit the seed button on the Projects page.</p></div>
      ) : (
        <div className="grid3" style={{ marginTop: 24 }}>
          {accounts.map(a => {
            const ready = (a.account_posts || []).length;
            const st = STATUS_LABELS[a.status] || { label: a.status, color: "var(--dim)" };
            return (
              <Link key={a.id} href={`/dashboard/projects/${pid}/accounts/${a.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                <div className="card" style={{ cursor: "pointer" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 28 }}>{a.avatar_emoji}</span>
                      {a.name}
                    </h3>
                  </div>
                  <p className="note" style={{ margin: "4px 0" }}>@{a.handle} · {a.platforms.join(", ")}</p>
                  <div style={{ marginTop: 8 }}>
                    <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 20, background: st.color + "22", color: st.color, border: "1px solid " + st.color }}>
                      {st.label}
                    </span>
                    {ready > 0 && <span style={{ fontSize: 11, marginLeft: 8, padding: "3px 10px", borderRadius: 20, background: "#10b98122", color: "#10b981" }}>{ready} posts</span>}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      <div className="card" style={{ marginTop: 32, maxWidth: 480 }}>
        <h3>Add an account</h3>
        <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
          <input placeholder="Account name (e.g. AI Tool Daily)" value={name} onChange={e=>setName(e.target.value)}
            style={{ background:"var(--bg)", border:"1px solid var(--line)", borderRadius:8, padding:"10px 12px", color:"inherit" }}/>
          <input placeholder="Handle (no @) — e.g. aitool_daily" value={handle} onChange={e=>setHandle(e.target.value)}
            style={{ background:"var(--bg)", border:"1px solid var(--line)", borderRadius:8, padding:"10px 12px", color:"inherit" }}/>
          <button onClick={add}>Create account → architect will build the brand kit</button>
        </div>
      </div>
    </div>
  );
}
