"use client";
import { useEffect, useState } from "react";
import Link from "next/link";

/* v5.8.9 — the "why is nothing happening?" answer, on screen.

   Every agent except Scout needs an ACTIVE account to have work. Scout is
   account-independent (it scouts trends globally), which is why a fully paused
   portfolio still shows a busy Scout feed and a silent everyone-else. That
   looked like "only 2 agents exist". It is actually "nothing has been switched on".

   This reads the real counts and states the blocker plainly. */

type Counts = { active: number; paused: number; ready: number; other: number; total: number };

export default function PipelineBlocker() {
  const [c, setCounts] = useState<Counts | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const r = await fetch("/api/projects/accounts-summary", { cache: "no-store" });
        if (!r.ok) return;
        const d = await r.json();
        if (live && d?.counts) setCounts(d.counts);
      } catch { /* advisory only */ }
    })();
    return () => { live = false; };
  }, []);

  if (!c || hidden) return null;
  if (c.active > 0) return null;   // something is switched on — nothing to warn about

  return (
    <div style={{
      border: "1px solid #f59e0b", borderRadius: 8, padding: "12px 14px",
      margin: "16px 0", background: "rgba(245,158,11,.07)", fontSize: 13.5,
    }}>
      <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
        <strong style={{ color: "#f59e0b" }}>⚠️ No account is active</strong>
        <span style={{ opacity: .8 }}>
          {c.total} accounts · {c.paused} paused · {c.ready} ready · {c.active} active
        </span>
        <button onClick={() => setHidden(true)} style={{
          marginLeft: "auto", background: "none", border: "1px solid var(--line)",
          color: "var(--dim)", borderRadius: 4, padding: "1px 8px", cursor: "pointer",
        }}>dismiss</button>
      </div>
      <p style={{ margin: "8px 0 0", opacity: .9 }}>
        Scout runs on its own — it looks for trends across the whole account list. Every other
        agent (Writer, Visuals, Voice, Editor, Grader, Publisher) only wakes up when an{" "}
        <b>active</b> account gives it a job. With everything paused they stay registered and
        idle, which is why the feed shows Scout and little else.
      </p>
      <p style={{ margin: "8px 0 0" }}>
        <Link href="/dashboard/projects" style={{ color: "#f59e0b" }}>
          Open a project → pick one account → <b>Resume this account</b>
        </Link>{" "}
        <span style={{ opacity: .7 }}>— start with one, not a hundred.</span>
      </p>
    </div>
  );
}
