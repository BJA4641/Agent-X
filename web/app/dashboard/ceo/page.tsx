"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

type Data = any;

export default function CEODashboard() {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState<string>("");
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const r = await fetch("/api/ceo", { cache: "no-store" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        setErr(j.error || `HTTP ${r.status}`);
        setD(null); return;
      }
      setD(await r.json()); setErr("");
    } catch (e: any) { setErr(e.message); }
    setLoading(false);
  }
  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i); }, []);

  if (loading) return <div className="p-8 text-white/70">Loading CEO dashboard…</div>;
  if (err) return <div className="p-8 text-red-400">Error: {err}. <Link className="underline" href="/dashboard">Back</Link></div>;
  if (!d) return null;

  const pct = Math.min(100, d.budget.pct);
  const budgetColor = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-emerald-500";

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto text-white space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">👔 CEO Scorecard</h1>
          <p className="text-white/60">Agent-X v5.1 — autonomous media company, live status</p>
        </div>
        <div className="flex gap-2">
          <span className={`px-3 py-1 rounded-full text-xs ${d.budget.killswitch ? "bg-red-600" : "bg-emerald-600"}`}>
            KILL SWITCH: {d.budget.killswitch ? "ON (PAUSED)" : "off"}
          </span>
          <Link href="/dashboard" className="px-3 py-1 rounded bg-white/10 text-xs">← Dashboard</Link>
        </div>
      </header>

      {/* Top metrics */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Metric label="Spend today" value={`$${d.budget.spent_usd.toFixed(3)} / $${d.budget.cap_usd.toFixed(2)}`} accent={pct>90?"red":pct>70?"yellow":"emerald"} />
        <Metric label="Published 24h" value={d.kpis.publishes_24h} />
        <Metric label="Views 24h" value={d.kpis.views_24h.toLocaleString()} />
        <Metric label="Open escalations" value={d.escalations_open} accent={d.escalations_open>0?"yellow":"emerald"} />
      </section>

      {/* Budget bar */}
      <section className="bg-white/5 rounded-2xl p-5 border border-white/10">
        <div className="flex justify-between text-sm mb-2">
          <span className="font-semibold">💰 CFO — daily budget</span>
          <span className="text-white/60">{pct.toFixed(0)}% used</span>
        </div>
        <div className="h-3 rounded-full bg-white/10 overflow-hidden">
          <div className={`h-full ${budgetColor} transition-all`} style={{ width: `${pct}%` }} />
        </div>
        <div className="text-xs text-white/50 mt-2">
          Auto-throttle: {d.budget.autothrottle?.on ? "ON" : "off"}
          {d.budget.autothrottle?.on ? ` (reserves ${Math.round((d.budget.autothrottle.reserve_fraction||0.1)*100)}%, delays low-priority work instead of stopping)` : ""}
        </div>
      </section>

      {/* Workers */}
      <section className="bg-white/5 rounded-2xl p-5 border border-white/10">
        <h2 className="font-semibold mb-3">🤖 Workers</h2>
        {d.workers.length === 0 && <div className="text-white/50 text-sm">No heartbeats yet — deploying or offline.</div>}
        <div className="space-y-2">
          {d.workers.map((w: any) => (
            <div key={w.worker_id} className="flex items-center justify-between text-sm bg-black/20 rounded-lg p-3">
              <div className="flex items-center gap-3">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${w.alive ? "bg-emerald-400 animate-pulse" : "bg-red-500"}`} />
                <div>
                  <div className="font-mono">{w.worker_id}</div>
                  <div className="text-xs text-white/50">{w.host || "?"} · v{w.version || "?"} · {w.seconds_since_hb}s ago</div>
                </div>
              </div>
              <div className="flex gap-3 text-xs text-white/70">
                <span>✅ {w.jobs_completed}</span>
                <span>❌ {w.jobs_failed}</span>
                <span>⏳ {w.jobs_in_progress}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="grid md:grid-cols-2 gap-4">
        <Panel title="📥 Job queue (v5 engine)">
          <Row label="Queued"         v={d.pipeline.queued} />
          <Row label="Claimed"        v={d.pipeline.claimed} />
          <Row label="In progress"    v={d.pipeline.in_progress} />
          <Row label="Waiting human"  v={d.pipeline.wait_human} accent={d.pipeline.wait_human>0?"yellow":undefined} />
          <Row label="Done today"     v={d.pipeline.done_today} />
          <Row label="Failed today"   v={d.pipeline.failed_today} accent={d.pipeline.failed_today>0?"red":undefined} />
        </Panel>
        <Panel title="🎬 Content board">
          <Row label="Ideas"     v={d.board.idea} />
          <Row label="Drafted"   v={d.board.drafted} />
          <Row label="Approved"  v={d.board.approved} />
          <Row label="Scheduled" v={d.board.scheduled} />
          <Row label="Published" v={d.board.published} accent="emerald" />
          <Row label="Rejected"  v={d.board.rejected} />
          <Row label="Failed"    v={d.board.failed} accent={d.board.failed>0?"red":undefined} />
          <Row label="Reported"  v={d.board.reported} />
        </Panel>
      </section>

      <section className="bg-white/5 rounded-2xl p-5 border border-white/10">
        <h2 className="font-semibold mb-3">👤 Human desk</h2>
        <p className="text-white/60 text-sm">
          Agents pause and escalate risky decisions (sponsorships, ban-risk, final brand choices).
          You can see and resolve them from <Link className="underline" href="/dashboard/workspace">the workspace</Link>
          {" "}(future UI panel in v5.1.x). Currently <b>{d.escalations_open}</b> open.
        </p>
      </section>

      <div className="text-center text-xs text-white/40 pt-4">
        auto-refreshes every 15s · v5.1 phase 3
      </div>
    </div>
  );
}

function Metric({ label, value, accent }: { label: string; value: any; accent?: "emerald"|"yellow"|"red" }) {
  const color = !accent ? "border-white/10" : accent==="red" ? "border-red-500/40" : accent==="yellow" ? "border-yellow-500/40" : "border-emerald-500/40";
  return (
    <div className={`bg-white/5 rounded-2xl p-4 border ${color}`}>
      <div className="text-xs text-white/50 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: any }) {
  return (
    <div className="bg-white/5 rounded-2xl p-5 border border-white/10">
      <h2 className="font-semibold mb-3">{title}</h2>
      <div className="space-y-1 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, v, accent }: { label: string; v: number; accent?: "emerald"|"yellow"|"red" }) {
  const dot = !accent ? "text-white/80" : accent==="red" ? "text-red-400" : accent==="yellow" ? "text-yellow-400" : "text-emerald-400";
  return (
    <div className="flex justify-between">
      <span className="text-white/60">{label}</span>
      <span className={`font-mono ${dot}`}>{v}</span>
    </div>
  );
}
