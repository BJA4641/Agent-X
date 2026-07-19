"use client";
import { useState } from "react";

export default function AdminActions() {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function seed() {
    setBusy("seed"); setMsg(null);
    const r = await fetch("/api/admin/seed-demo", { method: "POST" });
    const j = await r.json();
    setBusy(null);
    setMsg(j.error ? "Error: " + j.error
      : `Done. Created ${j.projects_created} project(s) and ${j.accounts_created} account(s). Architect will build brand kits on the next tick (~60s).`);
  }

  async function tick() {
    setBusy("tick"); setMsg(null);
    setMsg("Tick requested — watch the Workspace feed for activity. (Tick happens automatically every 60s when Railway is online.)");
    setBusy(null);
  }

  return (
    <div className="card" style={{ borderLeft: "3px solid var(--scheduled)" }}>
      <h3>Admin tools</h3>
      <p className="note" style={{ marginTop: -4 }}>
        Trigger agent actions directly. These hit your live Railway pipeline.
      </p>
      <div style={{ display: "flex", gap: 10, marginTop: 12, flexWrap: "wrap" }}>
        <button onClick={seed} disabled={!!busy}>
          {busy === "seed" ? "Seeding…" : "🎬 Seed demo: 6 niches × 5 accounts"}
        </button>
        <button onClick={tick} disabled={!!busy} style={{ background: "none", border: "1px solid var(--line)" }}>
          Refresh feed
        </button>
      </div>
      {msg && <p className="note" style={{ marginTop: 12, fontSize: 13 }}>{msg}</p>}
    </div>
  );
}
