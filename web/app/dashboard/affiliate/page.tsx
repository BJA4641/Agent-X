// web/app/dashboard/affiliate/page.tsx
// v5.9.8 REQ-WEB-404: the sidebar has linked here since the "Social platforms"
// group shipped, but the page never existed — the link returned a 404, which is
// why these modules read as "missing" when they were only ever menu entries.
"use client";
import { useEffect, useState } from "react";

type Link = { id?: string; label: string; url: string; program?: string; clicks?: number };

export default function AffiliatePage() {
  const [links, setLinks] = useState<Link[]>([]);
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [program, setProgram] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const r = await fetch("/api/affiliate", { cache: "no-store" });
      if (r.ok) { const j = await r.json(); setLinks(j.links || []); }
    } catch { /* endpoint may not exist yet — page still renders */ }
  }
  useEffect(() => { load(); }, []);

  async function add() {
    if (!label.trim() || !url.trim()) { setErr("Label and URL are both required."); return; }
    setBusy(true); setErr("");
    try {
      const r = await fetch("/api/affiliate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, url, program }),
      });
      if (!r.ok) throw new Error(await r.text());
      setLabel(""); setUrl(""); setProgram(""); await load();
    } catch (e: any) {
      setErr("Could not save — the affiliate API is not wired yet. Your link was not stored.");
    } finally { setBusy(false); }
  }

  return (
    <div>
      <h1>Affiliate links</h1>
      <p className="lead">The products and tools your content links to. One clear CTA per post
        converts better than several — the writer picks the most relevant link for each topic.</p>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Add a link</h3>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr", marginTop: 12 }}>
          <input placeholder="Label shown in captions (e.g. 'My camera')"
                 value={label} onChange={e => setLabel(e.target.value)} />
          <input placeholder="Program (Amazon Associates, Lemon Squeezy…)"
                 value={program} onChange={e => setProgram(e.target.value)} />
        </div>
        <input placeholder="https://…" value={url} onChange={e => setUrl(e.target.value)}
               style={{ marginTop: 10, width: "100%" }} />
        <button onClick={add} disabled={busy} style={{ marginTop: 12 }}>
          {busy ? "Saving…" : "Add link"}
        </button>
        {err && <p className="note" style={{ color: "var(--danger, #d33)" }}>{err}</p>}
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Your links {links.length > 0 && <span className="note">({links.length})</span>}</h3>
        {links.length === 0 ? (
          <p className="note">No links yet. Add one above and it becomes available to the
            monetization step when a post is a genuine fit.</p>
        ) : (
          <table style={{ width: "100%", marginTop: 10 }}>
            <thead><tr><th align="left">Label</th><th align="left">Program</th><th align="left">URL</th><th align="right">Clicks</th></tr></thead>
            <tbody>
              {links.map((l, i) => (
                <tr key={l.id || i}>
                  <td>{l.label}</td>
                  <td className="note">{l.program || "—"}</td>
                  <td className="note" style={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis" }}>{l.url}</td>
                  <td align="right">{l.clicks ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Honest disclosure</h3>
        <p className="note">Affiliate relationships must be disclosed. The caption writer appends a
          disclosure automatically when a post carries an affiliate link. Do not remove it — platforms
          and the FTC both require it, and removing it puts the account at risk.</p>
      </div>
    </div>
  );
}
