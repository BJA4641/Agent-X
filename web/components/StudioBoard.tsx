"use client";
import { useState } from "react";

type Item = { id: string; status: string; topic: string; payload: any; created_at: string };
const ORDER = ["idea", "drafted", "approved", "scheduled", "published", "reported", "rejected", "failed"];
const COLOR: Record<string, string> = {
  idea: "var(--idea)", drafted: "var(--draft)", approved: "var(--approved)",
  scheduled: "var(--scheduled)", published: "var(--published)", reported: "var(--published)",
  rejected: "var(--dim)", failed: "#e5484d",
};

export default function StudioBoard({ items, killOn, softOn, econOn }: { items: Item[]; killOn: boolean; softOn?: boolean; econOn?: boolean }) {
  const [rows, setRows] = useState(items);
  const [kill, setKill] = useState(killOn);
  const [soft, setSoft] = useState(!!softOn);
  const [econ, setEcon] = useState(!!econOn);
  const [busy, setBusy] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const REASONS = ["weak hook", "boring visuals", "off topic", "too generic", "wrong tone"];

  function copyFor(it: Item, platform: "instagram" | "tiktok" | "youtube") {
    const caps = it.payload?.captions || {};
    let text = "";
    if (platform === "instagram" && caps.instagram) {
      text = caps.instagram.caption + "\n\n" + (caps.instagram.hashtags || []).map((h: string) => "#" + h).join(" ");
    } else if (platform === "tiktok" && caps.tiktok) {
      text = caps.tiktok.caption + "\n\n" + (caps.tiktok.hashtags || []).map((h: string) => "#" + h).join(" ");
    } else if (platform === "youtube" && caps.youtube) {
      text = "TITLE: " + (caps.youtube.title || "") + "\n\nDESCRIPTION:\n" + (caps.youtube.description || "")
        + (caps.youtube.tags ? "\n\nTAGS: " + caps.youtube.tags.join(", ") : "");
    }
    if (!text) return;
    navigator.clipboard.writeText(text);
    setBusy("copied-" + platform + "-" + it.id);
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
    else if (j.soft !== undefined) setSoft(j.soft);
    else if (j.econ !== undefined) setEcon(j.econ);
    else setKill(j.kill);
  }

  const grouped = ORDER.map((s) => [s, rows.filter((r) => r.status === s)] as const).filter(([, v]) => v.length);
  return (
    <>
      <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20, gap: 10, flexWrap: "wrap" }}>
        <span><b>Worker:</b>{" "}
          <span style={{ color: kill ? "#e5484d" : soft ? "#f59e0b" : "var(--approved)" }}>
            {kill ? "STOPPED (emergency stop on)" : soft ? "INTAKE PAUSED (finishing in-flight work)" : "running"}
          </span>
        </span>
        <span style={{ display: "flex", gap: 8 }}>
          {!kill && (<>
            <button className="ghost" style={soft ? { borderColor: "#f59e0b", color: "#f59e0b" } : {}}
              onClick={() => act(soft ? "soft_pause_off" : "soft_pause_on")}
              disabled={busy === "soft_pause_on" || busy === "soft_pause_off"}
              title="Take no NEW content work, but let anything mid-render finish. Gentle brake.">
              {soft ? "Resume intake" : "Pause intake"}
            </button>
            <button className="ghost" style={econ ? { borderColor: "#22c55e", color: "#22c55e" } : {}}
              onClick={() => act(econ ? "econ_off" : "econ_on")}
              disabled={busy === "econ_on" || busy === "econ_off"}
              title="Econ mode: visuals prefer free providers (Gemini free tier → procedural). Paid image calls are skipped. LLM free-preference lands in v5.8.1.">
              {econ ? "💚 Econ mode ON" : "Econ mode"}
            </button>
          </>)}
          <button className={kill ? "primary" : "ghost"} onClick={() => act(kill ? "kill_off" : "kill_on")}
            disabled={busy === "kill_on" || busy === "kill_off"}
            title="Hard stop: worker refuses ALL paid work immediately. Nothing is lost; Resume picks the queue back up.">
            {kill ? "Resume worker" : "Emergency stop"}
          </button>
        </span>
      </div>
      {grouped.length === 0 && <p className="note">Board is empty. Run <code className="mono">python cli.py tick</code> on the worker to fill it.</p>}
      {grouped.map(([status, list]) => (
        <div key={status} style={{ marginBottom: 24 }}>
          <h3 style={{ color: COLOR[status], fontFamily: "var(--font-mono)", fontSize: 13, textTransform: "uppercase", letterSpacing: ".1em", marginBottom: 8 }}>
            {status} · {list.length}
          </h3>
          <div className="steps boardcols">
            {list.map((it) => (
              <div className="step" key={it.id} style={{ borderLeft: `3px solid ${COLOR[it.status]}` }}>
                <span style={{ flex: 1 }}>
                  <h4>{it.topic}</h4>
                  <p className="mono" style={{ fontSize: 11 }}>{it.id.slice(0, 8)} · {new Date(it.created_at).toLocaleString()}</p>
                  {it.status === "idea" && (
                    <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                      {it.payload?.bucket && <span className="tag">{it.payload.bucket}</span>}
                      {it.payload?.queued_by && <span className="tag">via {it.payload.queued_by}</span>}
                      {it.payload?.attempts && <span className="tag" style={{ color: "#e5484d" }}>render attempt {it.payload.attempts}/3</span>}
                      {it.payload?.source && <a href={it.payload.source} target="_blank" rel="noreferrer" style={{ color: "var(--scheduled)", fontSize: 13 }}>source ↗</a>}
                      <p className="note" style={{ width: "100%", margin: "4px 0 0" }}>An idea is just a topic on the belt — nothing is written yet. The writer drafts it next tick, the art dept renders it, and it comes back here as <b>drafted</b> with video + captions for your approval.</p>
                    </div>
                  )}
                  {it.status === "failed" && it.payload?.error && (
                    <p className="note mono" style={{ color: "#e5484d", marginTop: 6, whiteSpace: "pre-wrap" }}>{it.payload.error}</p>
                  )}
                  {it.payload?.video_url && (
                    <div style={{ marginTop: 10 }}>
                      <video src={it.payload.video_url} controls preload="metadata"
                             style={{ width: 180, borderRadius: 8, border: "1px solid var(--line)" }} />
                      <div><a href={it.payload.video_url} download target="_blank" rel="noreferrer"
                           style={{ fontSize: 13, color: "var(--approved)" }}>⬇ Download reel (post this file)</a></div>
                    </div>
                  )}
                  {Array.isArray(it.payload?.carousel_urls) && it.payload.carousel_urls.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      <div style={{ display: "flex", gap: 6, overflowX: "auto", maxWidth: 460 }}>
                        {it.payload.carousel_urls.map((u: string, i: number) => (
                          <a key={u} href={u} target="_blank" rel="noreferrer" title={`Open slide ${i + 1}`}>
                            <img src={u} alt={`slide ${i + 1}`}
                                 style={{ width: 84, height: 105, objectFit: "cover", borderRadius: 6, border: "1px solid var(--line)" }} />
                          </a>
                        ))}
                      </div>
                      <p className="note" style={{ marginTop: 4 }}>
                        🖼️ Carousel — open each slide → save image → post as an IG carousel / TikTok photo post.
                        {Array.isArray(it.payload?.captions?.post_windows) && it.payload.captions.post_windows.length > 0 &&
                          <> Best times: {it.payload.captions.post_windows.join(" · ")}</>}
                      </p>
                    </div>
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
                      {it.payload.captions.tiktok?.sound_note && (
                        <p className="note" style={{ marginTop: 6 }}>TikTok sound: {it.payload.captions.tiktok.sound_note}</p>
                      )}
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                        <button className="ghost" style={{ fontSize: 13 }} onClick={() => copyFor(it, "instagram")}>
                          {busy === "copied-instagram-" + it.id ? "Copied ✓" : "Copy IG"}
                        </button>
                        {it.payload.captions.tiktok && (
                          <button className="ghost" style={{ fontSize: 13 }} onClick={() => copyFor(it, "tiktok")}>
                            {busy === "copied-tiktok-" + it.id ? "Copied ✓" : "Copy TikTok"}
                          </button>
                        )}
                        {it.payload.captions.youtube && (
                          <button className="ghost" style={{ fontSize: 13 }} onClick={() => copyFor(it, "youtube")}>
                            {busy === "copied-youtube-" + it.id ? "Copied ✓" : "Copy YT title+desc"}
                          </button>
                        )}
                        {it.payload?.video_url && (
                          <a className="ghost" style={{ fontSize: 13, textDecoration: "none", padding: "6px 12px", border: "1px solid var(--line)", borderRadius: 8 }}
                             href={it.payload.video_url} download target="_blank" rel="noreferrer">Download video ↓</a>
                        )}
                      </div>
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
