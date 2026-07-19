"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

type Project = { id: string; name: string; niche: string; platforms: string[]; active: boolean; created: string };

const DEFAULT_PROJECTS: Project[] = [
  { id: "main", name: "My AI tools page", niche: "ai_tools", platforms: ["instagram","youtube","tiktok"], active: true, created: new Date().toISOString() },
];

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>(DEFAULT_PROJECTS);
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("ai_tools");

  useEffect(() => {
    const saved = localStorage.getItem("agentx_projects");
    if (saved) { try { setProjects(JSON.parse(saved)); } catch {} }
  }, []);
  useEffect(() => { localStorage.setItem("agentx_projects", JSON.stringify(projects)); }, [projects]);

  function add() {
    if (!name.trim()) return;
    setProjects([...projects, {
      id: Date.now().toString(), name: name.trim(), niche, platforms: [],
      active: false, created: new Date().toISOString(),
    }]);
    setName("");
  }
  function toggle(id: string) {
    setProjects(projects.map(p => ({ ...p, active: p.id === id })));
  }
  function remove(id: string) {
    setProjects(projects.filter(p => p.id !== id));
  }

  return (
    <div>
      <h1>Projects</h1>
      <p className="lead">Run multiple pages and brands from one account. Only one project is <b>active</b> at a time — agents work on the active project.</p>

      <div className="grid3" style={{ marginTop: 24 }}>
        {projects.map(p => (
          <div key={p.id} className="card" style={{ borderColor: p.active ? "var(--approved)" : undefined }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              {p.active
                ? <span className="tag" style={{ background: "var(--approved)", color: "#000" }}>active</span>
                : <button onClick={() => toggle(p.id)} className="tag" style={{ cursor: "pointer", border: "none" }}>make active</button>}
            </div>
            <p className="note" style={{ margin: "8px 0" }}>{p.niche} · {p.platforms.length ? p.platforms.join(", ") : "no platforms yet"}</p>
            <div style={{ display: "flex", gap: 10 }}>
              <Link href="/dashboard/workspace" style={{ color: "var(--scheduled)", fontSize: 13 }}>open workspace →</Link>
              {!p.active && <button onClick={() => remove(p.id)} style={{ color: "var(--failed)", fontSize: 12, background: "none", border: "none", cursor: "pointer" }}>delete</button>}
            </div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 32, maxWidth: 480 }}>
        <h3>Start a new project</h3>
        <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
          <input placeholder="Project/brand name (e.g. Cat Care HQ)" value={name} onChange={(e) => setName(e.target.value)}
            style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" }} />
          <select value={niche} onChange={(e) => setNiche(e.target.value)}
            style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" }}>
            <option value="ai_tools">AI tools</option>
            <option value="fitness">Fitness</option>
            <option value="finance">Finance</option>
            <option value="cooking">Cooking</option>
            <option value="skincare">Skincare</option>
            <option value="gaming">Gaming</option>
            <option value="real_estate">Real estate</option>
            <option value="saas">SaaS</option>
            <option value="ecom">Ecommerce store</option>
          </select>
          <button onClick={add}>Create project</button>
        </div>
      </div>
    </div>
  );
}
