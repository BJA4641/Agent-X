"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Account = {
  id: string; name: string; handle: string; niche: string; platforms: string[];
  status: string; avatar_emoji: string; created_at: string; paused: boolean;
  daily_budget_usd: number;
  account_posts?: { status: string }[];
};

type Project = { id: string; name: string; niche: string; paused: boolean; daily_budget_usd: number; cta?: string };

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  needs_setup:   { label: "queued", color: "#64748b" },
  architecting:  { label: "architect building brand…", color: "#f59e0b" },
  strategizing:  { label: "strategist planning posts…", color: "#a78bfa" },
  ready:         { label: "ready", color: "#10b981" },
  paused:        { label: "paused", color: "#ef4444" },
  drafted:       { label: "drafted", color: "#a78bfa" },
  failed:        { label: "failed", color: "#ef4444" },
};

export default function ProjectDetailPage() {
  const { pid } = useParams<{ pid: string }>();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [name, setName] = useState("");
  const [handle, setHandle] = useState("");
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    const r = await fetch(`/api/projects/${pid}/accounts`, { cache: "no-store" });
    const j = await r.json();
    setAccounts(j.accounts || []);
    // Also fetch project info
    const pr = await fetch(`/api/projects`, { cache: "no-store" });
    const pj = await pr.json();
    const p = (pj.projects || []).find((x: Project) => x.id === pid);
    setProject(p || null);
    setLoading(false);
  }
  useEffect(() => { if (pid) refresh(); }, [pid]);
  useEffect(() => { if (pid) { const id = setInterval(refresh, 8000); return () => clearInterval(id); } }, [pid]);

  async function toggleProjectPaused() {
    if (!project) return;
    await fetch(`/api/projects`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: pid, paused: !project.paused }),
    });
    refresh();
  }

  async function toggleAccountPaused(aid: string, paused: boolean) {
    await fetch(`/api/projects/${pid}/accounts/${aid}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paused }),
    });
    refresh();
  }

  async function pauseAllOthers(keepId: string) {
    // Pause project? No — pause all accounts EXCEPT keepId, and resume keepId.
    for (const a of accounts) {
      const shouldPause = a.id !== keepId;
      if (shouldPause !== a.paused) {
        await fetch(`/api/projects/${pid}/accounts/${a.id}`, {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paused: shouldPause }),
        });
      }
    }
    if (project?.paused) await toggleProjectPaused();
    refresh();
  }

  async function add() {
    if (!name.trim()) return;
    await fetch(`/api/projects/${pid}/accounts`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), handle: handle.trim() || name.toLowerCase().replace(/\s+/g,"_") }),
    });
    setName(""); setHandle("");
    refresh();
  }

  const activeCount = accounts.filter(a => !a.paused).length;

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Link href="/dashboard/projects" className="note" style={{ fontSize: 13 }}>← All projects</Link>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0 }}>{project?.name || "Project"}</h1>
          <p className="lead" style={{ maxWidth: 640 }}>
            {project?.niche?.replace(/_/g," ")} · {accounts.length} accounts · {activeCount} active
          </p>
        </div>
        <button
          onClick={toggleProjectPaused}
          style={{ background: project?.paused ? "#10b981" : "#ef4444", border: "none" }}>
          {project?.paused ? "▶ Resume entire project" : "⏸ Pause entire project"}
        </button>
      </div>

      {project?.paused && (
        <div className="card" style={{ margin: "12px 0", borderColor: "#ef4444", background: "rgba(239,68,68,0.08)" }}>
          <b>⏸ Project is PAUSED</b>
          <p className="note" style={{ margin: "4px 0 0" }}>
            No agents will work on any account in this project until you resume.
          </p>
        </div>
      )}

      <p className="note" style={{ marginTop: 12 }}>
        💡 <b>Start with ONE account</b>: hit <i>"Run only this"</i> on one account — all others get paused, and the agents will keep
        rewriting drafts until content scores ≥8/10. When the posts look good, resume more.
      </p>

      {loading ? <p className="note">Loading accounts…</p> : accounts.length === 0 ? (
        <div className="card"><p className="note">No accounts yet. Add one below, or hit seed on Projects page.</p></div>
      ) : (
        <div className="grid3" style={{ marginTop: 24 }}>
          {accounts.map(a => {
            const ready = (a.account_posts || []).length;
            const st = STATUS_LABELS[a.status] || { label: a.status, color: "var(--dim)" };
            return (
              <div key={a.id} className="card" style={{ opacity: a.paused ? 0.55 : 1, borderColor: a.paused ? "#ef444466" : undefined }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                  <Link href={`/dashboard/projects/${pid}/accounts/${a.id}`} style={{ textDecoration: "none", color: "inherit", flex: 1 }}>
                    <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 28 }}>{a.avatar_emoji}</span>
                      {a.name}
                    </h3>
                    <p className="note" style={{ margin: "4px 0" }}>@{a.handle} · {a.platforms.join(", ")}</p>
                  </Link>
                </div>
                <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center" }}>
                  <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 20,
                                 background: a.paused ? "#ef444433" : st.color + "22",
                                 color: a.paused ? "#ef4444" : st.color,
                                 border: "1px solid " + (a.paused ? "#ef4444" : st.color) }}>
                    {a.paused ? "⏸ PAUSED" : st.label}
                  </span>
                  {ready > 0 && !a.paused && (
                    <span style={{ fontSize: 11, padding: "3px 10px", borderRadius: 20, background: "#10b98122", color: "#10b981" }}>
                      {ready} posts
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                  <Link href={`/dashboard/projects/${pid}/accounts/${a.id}`}
                        style={{ fontSize: 12, color: "var(--scheduled)", textDecoration: "none" }}>
                    Open →
                  </Link>
                  <button onClick={() => toggleAccountPaused(a.id, !a.paused)}
                          style={{ fontSize: 11, padding: "4px 10px", borderRadius: 6,
                                   background: a.paused ? "#10b98122" : "#ef444422",
                                   color: a.paused ? "#10b981" : "#ef4444",
                                   border: "1px solid " + (a.paused ? "#10b981" : "#ef4444"), cursor: "pointer" }}>
                    {a.paused ? "▶ Resume" : "⏸ Pause"}
                  </button>
                  <button onClick={() => pauseAllOthers(a.id)}
                          style={{ fontSize: 11, padding: "4px 10px", borderRadius: 6,
                                   background: "var(--scheduled)22", color: "var(--scheduled)",
                                   border: "1px solid var(--scheduled)", cursor: "pointer" }}>
                    ⚡ Run only this
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="card" style={{ marginTop: 32, maxWidth: 480 }}>
        <h3>Add an account</h3>
        <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
          <input placeholder="Account name (e.g. AI Tool Daily)" value={name} onChange={e=>setName(e.target.value)}
            style={{ background:"var(--bg)", border:"1px solid var(--line)", borderRadius:8, padding:"10px 12px", color:"inherit" }}/>
          <input placeholder="Handle (no @)" value={handle} onChange={e=>setHandle(e.target.value)}
            style={{ background:"var(--bg)", border:"1px solid var(--line)", borderRadius:8, padding:"10px 12px", color:"inherit" }}/>
          <button onClick={add}>Create account (starts paused)</button>
        </div>
      </div>
    </div>
  );
}
