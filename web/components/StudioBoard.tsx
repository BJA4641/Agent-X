"use client";
import { useState } from "react";

type Item = { id: string; status: string; topic: string; payload: any; created_at: string };
const ORDER = ["idea", "drafted", "approved", "scheduled", "published", "reported", "rejected", "failed"];
const COLOR: Record<string, string> = {
  idea: "var(--idea)", drafted: "var(--draft)", approved: "var(--approved)",
  scheduled: "var(--scheduled)", published: "var(--published)", reported: "var(--published)",
  rejected: "var(--dim)", failed: "#e5484d",
};

export default function StudioBoard({ items, killOn }: { items: Item[]; killOn: boolean }) {
  const [rows, setRows] = useState(items);
  const [kill, setKill] = useState(killOn);
  const [busy, setBusy] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const REASONS = ["weak hook", "boring visuals", "off topic", "too generic", "wrong tone"];

  function copyCaption(it: Item) {
    const ig = it.payload?.captions?.instagram;
    if (!ig) return;
    const text = ig.caption + "\n\n" + (ig.hashtags || []).map((h: string) => "#" + h).join(" ");
    navigator.clipboard.writeText(text);
    setBusy("copied-" + it.id);
    setTimeout(() => setBusy(null), 1200);
  }

  async function pickHook(itemId: string, hookIndex: number) {
    setBusy(itemId);
    const r = await fetch("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "pick_hook", itemId, hookIndex }) });
    const j = await r.json();
    if (j.ok) setRows(rows.map((x) => (x.id === itemId ? { ...x, payload: { ...x.payload, script: { ...x.payload.script, hook: j.hook }, hook_choice: { index: hookIndex } } } : x)));
    setBusy(null);
  }
  async function act(action: string, itemId?: string, reason?: string) {
    setBusy(itemId || action);
    const r = await fetch("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, itemId, reason }) });
    const j = await r.json();
    setBusy(null);
    if (!r.ok) { alert(j.error); return; }
    if (itemId) { setRows(rows.map((x) => (x.id === itemId ? { ...x, status: j.status } : x))); setRejecting(null); }
    else setKill(j.kill);
  }

  const grouped = ORDER.map((s) => [s, rows.filter((r) => r.status === s)] as const).filter(([, v]) => v.length);
  return (
    <>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <span><b>Worker:</b> <span style={{ color: kill ? "#e5484d" : "var(--approved)" }}>{kill ? "STOPPED (kill switch on)" : "running"}</span></span>
        <button className={kill ? "primary" : "ghost"} onClick={() => act(kill ? "kill_off" : "kill_on")} disabled={busy === "kill_on" || busy === "kill_off"}>
          {kill ? "Resume worker" : "Stop everything"}
        </button>
      </div>
      {grouped.length === 0 && <p className="note">Board is empty. Run <code className="mono">python cli.py tick</code> on the worker to fill it.</p>}
      {grouped.map(([status, list]) => (
        <div key={status} style={{ marginBottom: 24 }}>
          <h3 style={{ color: COLOR[status], fontFamily: "var(--font-mono)", fontSize: 13, textTransform: "uppercase", letterSpacing: ".1em", marginBottom: 8 }}>
            {status} · {list.length}
          </h3>
          <div className="steps">
            {list.map((it) => (
              <div className="step" key={it.id} style={{ borderLeft: `3px solid ${COLOR[it.status]}` }}>
                <span style={{ flex: 1 }}>
                  <h4>{it.topic}</h4>
                  <p className="mono" style={{ fontSize: 11 }}>{it.id.slice(0, 8)} · {new Date(it.created_at).toLocaleString()}</p>
                  {it.payload?.video_url && (
                    <video src={it.payload.video_url} controls preload="metadata"
                           style={{ width: 180, borderRadius: 8, marginTop: 10, border: "1px solid var(--line)" }} />
                  )}
                  {it.status === "drafted" && !it.payload?.video_url && (
                    <p className="note">No browser preview (worker had no Supabase storage) — check the file on the worker before approving.</p>
                  )}
                  {it.payload?.captions?.instagram && ["drafted", "approved", "scheduled"].includes(it.status) && (
                    <div style={{ marginTop: 10 }}>
                      <p className="mono" style={{ fontSize: 12, whiteSpace: "pre-wrap", color: "var(--dim)", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: 10, maxWidth: 420 }}>
                        {it.payload.captions.instagram.caption}
                        {"\n"}{(it.payload.captions.instagram.hashtags || []).map((h: string) => "#" + h).join(" ")}
                      </p>
                      <button className="ghost" style={{ marginTop: 6, fontSize: 13 }} onClick={() => copyCaption(it)}>
                        {busy === "copied-" + it.id ? "Copied ✓" : "Copy caption for manual post"}
                      </button>
                    </div>
                  )}
                  {it.payload?.metrics && <p className="note">{JSON.stringify(it.payload.metrics)}</p>}
                </span>
                {it.status === "drafted" && (it.payload?.script?.hook_options?.length > 1) && (
                  <span style={{ display: "grid", gap: 4 }}>
                    <p className="note">Pick the hook — this trains taste.</p>
                    {it.payload.script.hook_options.map((h: string, i: number) => (
                      <button key={i} className="ghost" disabled={busy === it.id}
                              style={{ fontSize: 13, textAlign: "left", borderColor: it.payload.script.hook === h ? "var(--approved)" : undefined, color: it.payload.script.hook === h ? "var(--approved)" : undefined }}
                              onClick={() => pickHook(it.id, i)}>{it.payload.script.hook === h ? "● " : "○ "}{h}</button>
                    ))}
                  </span>
                )}
                {it.status === "drafted" && rejecting !== it.id && (
                  <span style={{ display: "grid", gap: 8 }}>
                    <button className="primary" disabled={busy === it.id} onClick={() => act("approve", it.id)}>Approve</button>
                    <button className="ghost" disabled={busy === it.id} onClick={() => setRejecting(it.id)}>Reject</button>
                  </span>
                )}
                {it.status === "drafted" && rejecting === it.id && (
                  <span style={{ display: "grid", gap: 6 }}>
                    <p className="note">Why? This teaches the writer.</p>
                    {REASONS.map((r) => (
                      <button key={r} className="ghost" style={{ fontSize: 13 }} disabled={busy === it.id}
                              onClick={() => act("reject", it.id, r)}>{r}</button>
                    ))}
                    <button className="ghost" style={{ fontSize: 12, color: "var(--dim)" }} onClick={() => setRejecting(null)}>cancel</button>
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
