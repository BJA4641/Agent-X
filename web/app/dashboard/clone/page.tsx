"use client";
import { useState } from "react";

export default function ClonePage() {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"angle"|"mirror">("angle");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  async function analyze() {
    if (!url) return alert("Paste a video URL first.");
    setBusy(true); setResult(null);
    // Demo mode: queue the URL as an idea tagged 'clone-angle' so the writer produces an original on the same pattern.
    try {
      await fetch("/api/studio", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "queue_topic",
          topic: `[clone] original take on: ${url}`,
          source: url,
        }),
      });
      setResult(mode === "angle"
        ? "✓ Added to your Studio board. The writer will produce an ORIGINAL script using the same hook/structure but with different topic, words, and visuals — this is the only version platforms reward."
        : "✗ Mirror mode (straight reupload) disabled by default. Straight reposts trigger Content ID and demonetization. Switch to 'Clone the angle' for safe monetization."
      );
    } catch (e: any) { setResult(`Error: ${e.message}`); }
    setBusy(false);
  }

  return (
    <div>
      <h1>Clone viral</h1>
      <p className="lead">Turn any viral short into an original video that works the same psychological pattern — without reposting someone else's content (which gets you demonetized or banned).</p>

      <div className="card" style={{ marginTop: 20, padding: 24, maxWidth: 720 }}>
        <h3>Paste a viral video URL</h3>
        <p className="note" style={{ fontSize: 13 }}>YouTube, TikTok, Instagram Reel, or Shorts link. We'll transcribe it, reverse-engineer the hook and beat structure, and produce an original video in your niche.</p>
        <input type="url" placeholder="https://youtube.com/shorts/... or https://www.tiktok.com/@..."
               value={url} onChange={(e) => setUrl(e.target.value)}
               style={{ width: "100%", marginTop: 10, padding: "10px 12px", background: "var(--bg)",
                        border: "1px solid var(--line)", borderRadius: 8, color: "inherit" }} />

        <div style={{ marginTop: 14, display: "flex", gap: 12 }}>
          <label style={{ flex: 1, padding: 14, border: `2px solid ${mode==="angle" ? "var(--approved)" : "var(--line)"}`, borderRadius: 8, cursor: "pointer" }}>
            <input type="radio" name="mode" checked={mode === "angle"} onChange={() => setMode("angle")} />
            <b style={{ marginLeft: 6 }}>Clone the angle (recommended)</b>
            <p className="note" style={{ fontSize: 12, marginTop: 6, marginBottom: 0 }}>Original script & visuals, same viral structure. Safe, monetizable, algorithm-friendly.</p>
          </label>
          <label style={{ flex: 1, padding: 14, border: `2px solid ${mode==="mirror" ? "#e5484d" : "var(--line)"}`, borderRadius: 8, cursor: "pointer", opacity: 0.6 }}>
            <input type="radio" name="mode" checked={mode === "mirror"} onChange={() => setMode("mirror")} />
            <b style={{ marginLeft: 6 }}>Mirror / reupload</b>
            <p className="note" style={{ fontSize: 12, marginTop: 6, marginBottom: 0 }}>Exact copy. Risks copyright strikes, demonetization, bans. Disabled by default.</p>
          </label>
        </div>

        <button style={{ marginTop: 14 }} onClick={analyze} disabled={busy}>
          {busy ? "Analyzing…" : "Add to Studio board"}
        </button>

        {result && <p className="note" style={{ marginTop: 14 }}>{result}</p>}
      </div>

      <h2 style={{ marginTop: 36 }}>Why "clone the angle" makes you money</h2>
      <div className="grid">
        <div className="card">
          <h3>Platforms pay for ORIGINAL content</h3>
          <p className="note" style={{ fontSize: 13 }}>YouTube Creator Fund, Instagram ad revenue, and affiliate conversions all require original content. Reposted videos get claimed by Rights Manager or flagged as repurposed.</p>
        </div>
        <div className="card">
          <h3>Structure is the secret</h3>
          <p className="note" style={{ fontSize: 13 }}>A viral video's power is its structure — the hook pattern, beat timing, payoff. Swapping the topic and visuals keeps the formula, loses the risk.</p>
        </div>
        <div className="card">
          <h3>Monetization paths</h3>
          <p className="note" style={{ fontSize: 13 }}>Affiliate links (link-in-bio), YouTube Partner Program (1k subs + 4k watch hours), brand deals, and your own products — all available on original content only.</p>
        </div>
      </div>
    </div>
  );
}
