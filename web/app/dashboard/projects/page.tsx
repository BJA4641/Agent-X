"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

type Project = { id: string; name: string; niche: string; platforms: string[]; status: string; created_at: string; cta?: string };

const NICHE_EMOJI: Record<string,string> = {
  ai_tools: "🤖", finance: "💰", fitness: "💪", cooking: "🍳", skincare: "✨",
  saas: "🚀", gaming: "🎮", real_estate: "🏠", coaching: "🎯", ecom: "🛒",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("ai_tools");
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    const r = await fetch("/api/projects", { cache: "no-store" });
    const j = await r.json();
    setProjects(j.projects || []);
    setLoading(false);
  }
  useEffect(() => { refresh(); }, []);

  async function add() {
    if (!name.trim()) return;
    await fetch("/api/projects", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), niche }),
    });
    setName("");
    refresh();
  }
  async function remove(id: string) {
    if (!confirm("Delete this project and all its accounts/posts?")) return;
    await fetch("/api/projects?id=" + id, { method: "DELETE" });
    refresh();
  }
  async function seedDemo() {
    setSeeding(true); setSeedMsg(null);
    const r = await fetch("/api/admin/seed-demo", { method: "POST" });
    const j = await r.json();
    setSeeding(false);
    setSeedMsg(j.error ? ("Error: " + j.error)
      : `Created ${j.projects_created} projects and ${j.accounts_created} accounts. Architect agent will set them up on the next tick (~60s).`);
    refresh();
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
        <div>
          <h1 style={{ margin: 0 }}>Projects</h1>
          <p className="lead" style={{ maxWidth: 640 }}>
            Run multiple brands/niches from one account. Each project can hold several
            brand accounts, each with its own business plan, brand kit, tone, visual rules,
            and a queue of planned posts — all written by agents.
          </p>
        </div>
        <button onClick={seedDemo} disabled={seeding} style={{ background: "var(--scheduled)" }}>
          {seeding ? "Seeding…" : "🎬 Seed demo (6 niches × 5 accounts)"}
        </button>
      </div>

      {seedMsg && (
        <div className="card" style={{ margin: "16px 0", borderColor: "var(--approved)", background: "rgba(16,185,129,0.08)" }}>
          {seedMsg}
        </div>
      )}

      {loading ? <p className="note">Loading…</p> : projects.length === 0 ? (
        <div className="card"><p className="note">No projects yet. Create one below or click the seed button to fill the test suite.</p></div>
      ) : (
        <div className="grid3" style={{ marginTop: 24 }}>
          {projects.map(p => {
            const em = NICHE_EMOJI[p.niche] || "📁";
            return (
              <div key={p.id} className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ margin: 0 }}><span style={{ marginRight: 8 }}>{em}</span>{p.name}</h3>
                  <span className={"tag"} style={{
                    background: p.status === "active" ? "var(--approved)" : "var(--dim)",
                    color: p.status === "active" ? "#000" : "#fff"
                  }}>{p.status}</span>
                </div>
                <p className="note" style={{ margin: "8px 0" }}>{p.niche} · {p.platforms.length} platforms</p>
                {p.cta && <p style={{ fontSize: 12, color: "var(--dim)" }}>CTA: {p.cta}</p>}
                <div style={{ display: "flex", gap: 10, marginTop: 8, flexWrap: "wrap" }}>
                  <Link href={`/dashboard/projects/${p.id}`} style={{ color: "var(--scheduled)", fontSize: 13 }}>Open accounts →</Link>
                  <button onClick={() => remove(p.id)} style={{ color: "var(--failed)", fontSize: 12, background: "none", border: "none", cursor: "pointer" }}>delete</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="card" style={{ marginTop: 32, maxWidth: 480 }}>
        <h3>Start a new project</h3>
        <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
          <input placeholder="Project/brand name (e.g. Cat Care HQ)" value={name} onChange={(e) => setName(e.target.value)}
            style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" }} />
          <select value={niche} onChange={(e) => setNiche(e.target.value)}
            style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" }}>
            <option value="ai_tools">🤖 AI tools</option>
            <option value="finance">💰 Finance / side-hustle</option>
            <option value="fitness">💪 Fitness</option>
            <option value="cooking">🍳 Cooking</option>
            <option value="skincare">✨ Skincare</option>
            <option value="saas">🚀 SaaS / startups</option>
            <option value="gaming">🎮 Gaming</option>
            <option value="real_estate">🏠 Real estate</option>
            <option value="coaching">🎯 Coaching</option>
            <option value="ecom">🛒 Ecommerce store</option>
          </select>
          <button onClick={add}>Create project</button>
        </div>
      </div>
    </div>
  );
}
