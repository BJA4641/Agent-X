"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

type Project = { id: string; name: string; niche: string | null; status: string; created_at: string };

const NICHES = ["ai_tools","fitness","finance","cooking","skincare","gaming","real_estate","saas",
  "coaching","travel","fashion","parenting","crypto","music","pets","diy","cars","education",
  "productivity","mental_health"];

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("ai_tools");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    const r = await fetch("/api/projects");
    const j = await r.json();
    if (r.ok) setProjects(j.projects);
    const m = document.cookie.match(/(?:^|; )ax_project=([^;]+)/);
    if (m) setActiveId(decodeURIComponent(m[1]));
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  async function post(body: any) {
    setMsg("");
    const r = await fetch("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!r.ok) { setMsg(j.error || "Failed"); return false; }
    return true;
  }
  async function create() {
    if (!name.trim()) return;
    if (await post({ action: "create", name, niche })) { setName(""); load(); }
  }
  async function setActive(id: string) { if (await post({ action: "set_active", id })) setActiveId(id); }

  return (
    <div>
      <h1>Projects</h1>
      <p className="lead">
        Run several brands and niches from one account. The agents <b>plan content for every
        active project</b> on their own; the <b>selected</b> project below is where topics you
        queue by hand (Workspace, Trends, Clone) get filed.
      </p>
      {msg && <p className="note" style={{ color: "var(--failed)" }}>{msg}</p>}
      {loading ? <p className="note">Loading…</p> : (
      <div className="grid3" style={{ marginTop: 24 }}>
        {projects.map(p => (
          <div key={p.id} className="card" style={{ borderColor: p.id === activeId ? "var(--approved)" : undefined, opacity: p.status === "paused" ? 0.55 : 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              {p.id === activeId
                ? <span className="tag" style={{ background: "var(--approved)", color: "#000" }}>selected</span>
                : <button onClick={() => setActive(p.id)} className="tag" style={{ cursor: "pointer", border: "none" }}>select</button>}
            </div>
            <p className="note" style={{ margin: "8px 0" }}>{p.niche || "no niche"} · {p.status}</p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <Link href="/dashboard/workspace" style={{ color: "var(--scheduled)", fontSize: 13 }}>workspace →</Link>
              <Link href={"/trends"} style={{ color: "var(--scheduled)", fontSize: 13 }}>trends →</Link>
              {p.status === "active"
                ? <button onClick={async () => { await post({ action: "pause", id: p.id }); load(); }} style={btn}>pause</button>
                : <button onClick={async () => { await post({ action: "resume", id: p.id }); load(); }} style={btn}>resume</button>}
              <button onClick={async () => { if (confirm("Delete project? Existing items keep their tag but the project is gone.")) { await post({ action: "delete", id: p.id }); load(); } }}
                style={{ ...btn, color: "var(--failed)" }}>delete</button>
            </div>
          </div>
        ))}
        {projects.length === 0 && <p className="note">No projects yet — agents currently plan for your onboarding niche. Create a project to add another brand or niche.</p>}
      </div>)}

      <div className="card" style={{ marginTop: 32, maxWidth: 480 }}>
        <h3>Start a new project</h3>
        <p className="note">Each active project gets its own trend scouting and its own planned ideas. Paused projects are skipped — no budget spent on them.</p>
        <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
          <input placeholder="Project/brand name (e.g. Cat Care HQ)" value={name} onChange={e => setName(e.target.value)} style={inp} />
          <select value={niche} onChange={e => setNiche(e.target.value)} style={inp}>
            {NICHES.map(n => <option key={n} value={n}>{n.replace(/_/g, " ")}</option>)}
          </select>
          <button onClick={create}>Create project</button>
        </div>
      </div>
    </div>
  );
}
const inp = { background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" } as const;
const btn = { fontSize: 12, background: "none", border: "none", cursor: "pointer", color: "var(--muted)", padding: 0 } as const;
