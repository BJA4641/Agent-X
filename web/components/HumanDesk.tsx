"use client";
import { useEffect, useState } from "react";

type Esc = {
  id: string;
  severity: "ask"|"warn"|"kill";
  summary: string;
  options: {label:string;effect:string}[];
  created_at: string;
  deadline_hours: number;
  job_id?: string;
};

export default function HumanDesk() {
  const [escs, setEscs] = useState<Esc[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string|null>(null);

  async function load() {
    try {
      const r = await fetch("/api/human", { cache: "no-store" });
      if (!r.ok) return;
      const j = await r.json();
      setEscs(j.escalations || []);
    } catch {}
  }
  useEffect(() => { load(); const i=setInterval(load, 20000); return ()=>clearInterval(i); }, []);

  async function resolve(id: string, resolution: string, note="") {
    setBusy(id);
    try {
      await fetch("/api/human", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, resolution, note }),
      });
      await load();
    } finally { setBusy(null); }
  }

  if (!open && escs.length === 0) return null;

  return (
    <div className="rounded-2xl border border-yellow-400/40 bg-yellow-400/5 p-4 my-4">
      <button onClick={()=>setOpen(!open)} className="w-full flex items-center justify-between text-left">
        <div className="flex items-center gap-2">
          <span className="text-yellow-300 font-semibold">👤 Your approval needed</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-400/20 text-yellow-200">{escs.length} pending</span>
        </div>
        <span className="text-white/50 text-sm">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-2">
          {escs.length === 0 && <div className="text-sm text-white/50">No decisions waiting — agents are autonomous.</div>}
          {escs.map(e => (
            <div key={e.id} className="bg-black/30 rounded-lg p-3 text-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      e.severity==="kill" ? "bg-red-500/30 text-red-200" :
                      e.severity==="warn" ? "bg-yellow-500/30 text-yellow-200" :
                                           "bg-sky-500/30 text-sky-200"}`}>
                      {e.severity}
                    </span>
                    <span className="text-white/40 text-xs">{new Date(e.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-white/90 mt-1">{e.summary}</div>
                </div>
              </div>
              <div className="flex gap-2 mt-2 flex-wrap">
                {(e.options?.length ? e.options : [{label:"Approve",effect:"approve"},{label:"Reject",effect:"reject"}]).map(o => (
                  <button key={o.effect} disabled={busy===e.id}
                    onClick={()=>resolve(e.id, o.effect)}
                    className={`px-3 py-1 rounded text-xs font-medium ${
                      o.effect==="approve" ? "bg-emerald-500/30 hover:bg-emerald-500/50 text-emerald-100"
                                          : "bg-red-500/20 hover:bg-red-500/40 text-red-100"}`}>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
