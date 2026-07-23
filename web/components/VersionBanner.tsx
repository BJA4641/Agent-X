"use client";
import { useEffect, useState } from "react";

/* v5.8.7 — "which build is actually live?"
   A dismissible strip at the very top of every page showing the web version,
   the worker version reported by worker_health, and the heartbeat age.
   Dismissal is remembered per build: when a new version deploys the banner
   comes back on its own, so every push gets confirmed exactly once. */

type Info = {
  web: string;
  commit?: string | null;
  worker?: { version: string; heartbeat_age_s: number; alive: boolean; host?: string } | null;
  cost_mode?: string | null;
};

export default function VersionBanner() {
  const [info, setInfo] = useState<Info | null>(null);
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const r = await fetch("/api/version", { cache: "no-store" });
        const d: Info = await r.json();
        if (!live) return;
        setInfo(d);
        const stamp = `${d.web}|${d.worker?.version || "?"}|${d.commit || ""}`;
        let dismissed = "";
        try { dismissed = window.localStorage.getItem("agentx_ver_seen") || ""; } catch {}
        setHidden(dismissed === stamp);
      } catch { /* banner is cosmetic — never break the page */ }
    };
    load();
    const t = setInterval(load, 60_000);
    return () => { live = false; clearInterval(t); };
  }, []);

  if (!info || hidden) return null;

  const w = info.worker;
  const stale = !w || !w.alive;
  const mismatch = !!w && w.version !== info.web;
  const free = info.cost_mode === "free_only";

  // red = worker down · amber = versions disagree (a deploy is still rolling)
  // green = web and worker agree and the worker is beating
  const tone = stale ? "#ef4444" : mismatch ? "#f59e0b" : "#22c55e";

  const dismiss = () => {
    try {
      window.localStorage.setItem("agentx_ver_seen",
        `${info.web}|${w?.version || "?"}|${info.commit || ""}`);
    } catch {}
    setHidden(true);
  };

  return (
    <div role="status" style={{
      position: "relative",
      display: "flex", alignItems: "center", justifyContent: "center",
      gap: 12, flexWrap: "wrap",
      padding: "7px 96px 7px 14px", fontSize: 12.5, lineHeight: 1.4,
      fontFamily: "var(--font-mono, ui-monospace, monospace)",
      background: "rgba(0,0,0,.55)", borderBottom: `1px solid ${tone}`, color: "#e5e7eb",
      textAlign: "center",
    }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: tone, flex: "0 0 auto" }} />
      <strong style={{ color: tone }}>LIVE BUILD</strong>
      <span>web <b>v{info.web}</b></span>
      <span style={{ opacity: .5 }}>·</span>
      <span>worker <b>{w ? `v${w.version}` : "no heartbeat"}</b></span>
      {w && <><span style={{ opacity: .5 }}>·</span>
        <span>beat {w.heartbeat_age_s}s ago</span></>}
      {info.commit && <><span style={{ opacity: .5 }}>·</span>
        <span title="Vercel git commit">{info.commit.slice(0, 7)}</span></>}
      {free && <span style={{ color: "#22c55e", border: "1px solid #22c55e",
        borderRadius: 4, padding: "1px 6px" }}>FREE-ONLY MODE</span>}
      {stale && <span style={{ color: "#ef4444" }}>
        worker is not beating — check Railway</span>}
      {!stale && mismatch && <span style={{ color: "#f59e0b" }}>
        versions disagree — the worker has not picked up this push yet</span>}
      {!stale && !mismatch && <span style={{ opacity: .7 }}>web and worker agree ✓</span>}
      <button onClick={dismiss} aria-label="Dismiss"
        style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
          background: "none", border: "1px solid #4b5563",
          color: "#9ca3af", borderRadius: 4, padding: "1px 8px", cursor: "pointer" }}>
        dismiss
      </button>
    </div>
  );
}
