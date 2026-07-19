"use client";
import { useEffect, useState } from "react";

type Event = {
  id: number;
  agent: string;
  action: string;
  message: string | null;
  status: "info" | "success" | "warn" | "error" | "debate";
  cost_usd: number;
  created_at: string;
  item_id: string | null;
};

const AGENT_COLORS: Record<string, string> = {
  strategy: "#9b6bff", brain: "#66fcf1", critique: "#f5a524", visuals: "#4cc9f0",
  voice: "#ff6b9d", captions: "#a8e063", produce: "#66d9ef", qa: "#ffd166",
  publish_ig: "#e1306c", publish_yt: "#ff0000", community: "#74c69d", digest: "#48cae4",
  planner: "#b5179e", brand: "#ff8500",
};

const AGENT_LABELS: Record<string, string> = {
  strategy: "Strategist", brain: "Writer", critique: "Critic", visuals: "Art Dept",
  voice: "Voice", captions: "Captions", produce: "Renderer", qa: "Editor",
  publish_ig: "IG Publisher", publish_yt: "YT Publisher", community: "Community",
  digest: "Analyst", planner: "Planner", brand: "Brand",
};

function statusColor(s: string) {
  return ({ success: "var(--published)", warn: "var(--draft)",
    error: "#e5484d", debate: "#9b6bff", info: "var(--dim)" } as any)[s] || "var(--dim)";
}

export default function WorkspacePage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [filter, setFilter] = useState<string>("all");

  async function load() {
    const r = await fetch("/api/workspace/events", { cache: "no-store" });
    if (r.ok) {
      const j = await r.json();
      setEvents(j.events || []);
    }
  }
  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const agents = Array.from(new Set(events.map((e) => e.agent)));
  const filtered = filter === "all" ? events : events.filter((e) => e.agent === filter);

  const totalSpend = events.reduce((a, e) => a + Number(e.cost_usd || 0), 0);
  const success = events.filter((e) => e.status === "success").length;
  const errors = events.filter((e) => e.status === "error").length;

  return (
    <div>
      <h1>Agent workspace</h1>
      <p className="lead">Live feed of every agent working on your content. Click an agent to filter.</p>

      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <p className="note">Total events</p>
          <h2 style={{ margin: 0 }}>{events.length}</h2>
        </div>
        <div className="card">
          <p className="note">Spend to date</p>
          <h2 style={{ margin: 0 }}>${totalSpend.toFixed(3)}</h2>
        </div>
        <div className="card">
          <p className="note">Success / errors</p>
          <h2 style={{ margin: 0 }}>{success} · <span style={{ color: "#e5484d" }}>{errors}</span></h2>
        </div>
      </div>

      <div style={{ marginTop: 24, display: "flex", gap: 6, flexWrap: "wrap" }}>
        <button className={filter === "all" ? "primary" : "ghost"} onClick={() => setFilter("all")}>All</button>
        {agents.map((a) => (
          <button key={a} className={filter === a ? "primary" : "ghost"} onClick={() => setFilter(a)}
                  style={{ borderLeft: `3px solid ${AGENT_COLORS[a] || "#888"}`, paddingLeft: 10 }}>
            {AGENT_LABELS[a] || a}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginTop: 14, padding: 0, overflow: "hidden" }}>
        {filtered.length === 0 && <div className="honest" style={{ padding: 24 }}>Waiting for agents to start work… produce your first video from Studio to see activity.</div>}
        {filtered.map((e) => (
          <div key={e.id} style={{ display: "flex", gap: 12, padding: "12px 16px", borderBottom: "1px solid var(--line)", fontSize: 14 }}>
            <span className="mono" style={{ color: "var(--dim)", width: 70, fontSize: 11, paddingTop: 3 }}>
              {new Date(e.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
            <span style={{
              background: AGENT_COLORS[e.agent] || "#444",
              color: "#000", borderRadius: 6, padding: "2px 8px", fontSize: 11,
              fontWeight: 600, alignSelf: "flex-start", marginTop: 1, whiteSpace: "nowrap",
            }}>{AGENT_LABELS[e.agent] || e.agent}</span>
            <span style={{ flex: 1 }}>
              <b>{e.action}</b>
              {e.message && <span style={{ color: "var(--dim)" }}> — {e.message}</span>}
              {e.item_id && <span className="mono" style={{ marginLeft: 8, fontSize: 11, color: "var(--dim)" }}>{e.item_id.slice(0, 8)}</span>}
            </span>
            <span style={{ color: statusColor(e.status), fontSize: 11, whiteSpace: "nowrap" }}>
              {e.cost_usd > 0 && `$${Number(e.cost_usd).toFixed(3)} · `}{e.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
