"use client";
import { useEffect, useState } from "react";

type Model = {
  id: string; name: string; provider: string;
  paid: boolean; free_tier: boolean;
  est_usd: number | null; has_key: boolean; key_env: string | null;
  arena_rank: number | null; best_for: string | null;
};
type Cat = { label: string; defaults: string[]; models: Model[] };
type Data = { catalog: Record<string, Cat>; chosen: Record<string, any> };

const CAT_EMOJI: Record<string, string> = {
  text: "💬", text_to_image: "🖼️", image_edit: "✏️",
  text_to_video: "🎬", image_to_video: "🎞️", voice: "🎙️", video_edit: "🎞️",
};
const CAT_ROUTE: Record<string, string> = {
  text: "model", text_to_image: "model_t2i", image_edit: "model_ie",
  text_to_video: "model_t2v", image_to_video: "model_i2v", voice: "model_tts", video_edit: "model_vedit",
};

export default function ModelsAdminPage() {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState<Record<string, string>>({});
  const [tab, setTab] = useState("text_to_image");

  const load = async () => {
    setLoading(true); setErr("");
    try {
      const r = await fetch("/api/ai-models", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || "failed");
      setData(j);
    } catch (e: any) { setErr(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const setDefault = async (category: string, model_id: string) => {
    setMsg(m => ({ ...m, [category]: "saving…" }));
    const r = await fetch("/api/ai-models", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, model_id }),
    });
    const j = await r.json();
    setMsg(m => ({ ...m, [category]: r.ok ? `✓ default set to ${model_id.split("-").slice(0,2).join("-")}` : (j.error || "fail") }));
    if (r.ok) load();
  };

  if (loading) return <div><h1>AI models</h1><p className="note">Loading…</p></div>;
  if (err) return <div><h1>AI models</h1><p className="note" style={{color:"#ef4444"}}>{err}</p></div>;
  if (!data) return null;

  const cats = Object.entries(data.catalog);

  return (
    <div>
      <h1>AI models <span className="tag" style={{marginLeft:8, fontSize:11}}>v5.4</span></h1>
      <p className="note" style={{maxWidth:760}}>
        <b>Every AI your agents can use,</b> organized by job type. Agents automatically pick the
        top-rated model that has an API key loaded and falls back to free tiers when paid wallets
        are empty or fail. Set your default per category below. Add API keys in Railway / Vercel
        env vars — the names are shown next to each model.
      </p>
      <div className="note" style={{maxWidth:760, padding:"10px 14px", border:"1px solid var(--line)", borderRadius:8, marginTop:10}}>
        <b>Auto-fallback:</b> if the chosen model fails (no key, out of credits, overloaded),
        agents automatically rotate down the list → free tier last. Production never stops.
      </div>

      {/* Tabs */}
      <div style={{display:"flex", gap:6, flexWrap:"wrap", marginTop:20, marginBottom:16}}>
        {cats.map(([k, c]) => {
          const chosen = data.chosen[CAT_ROUTE[k]]?.model || c.defaults[0];
          const readyCount = c.models.filter(m => m.has_key || m.free_tier).length;
          return (
            <button key={k} onClick={() => setTab(k)}
              className={tab === k ? "primary" : ""}
              style={{
                padding:"8px 12px", borderRadius:8, cursor:"pointer",
                border:"1px solid var(--line)", background: tab===k?"var(--approved)":"var(--card)",
                color: tab===k?"#fff":"inherit", fontSize:13,
              }}>
              {CAT_EMOJI[k]||"•"} {c.label.split(" (")[0]}
              <span className="tag" style={{marginLeft:6, fontSize:10, opacity:0.8}}>{readyCount}/{c.models.length}</span>
            </button>
          );
        })}
      </div>

      {/* Active category */}
      {cats.filter(([k]) => k === tab).map(([k, c]) => {
        const chosen = data.chosen[CAT_ROUTE[k]]?.model || c.defaults[0];
        return (
          <div key={k}>
            <h2 style={{marginTop:4}}>{CAT_EMOJI[k]} {c.label}</h2>
            <p className="note" style={{marginTop:-4}}>
              Current default: <b className="mono">{chosen || "not set"}</b>
              {msg[k] && <span style={{marginLeft:12, color:"var(--approved)"}}>{msg[k]}</span>}
            </p>
            <div style={{display:"grid", gap:8, marginTop:10}}>
              {c.models.map((m) => {
                const isChosen = m.id === chosen;
                return (
                  <div key={m.id} className="card" style={{
                    padding:12, display:"grid", gridTemplateColumns:"auto 1fr auto", gap:12, alignItems:"center",
                    borderLeft: `4px solid ${isChosen ? "var(--approved)" : m.free_tier?"var(--published, #22c55e)":"var(--line)"}`,
                    opacity: (!m.has_key && !m.free_tier) ? 0.5 : 1,
                  }}>
                    <div style={{display:"flex", flexDirection:"column", alignItems:"center", minWidth:64, gap:4}}>
                      <span style={{fontSize:10, fontWeight:700, letterSpacing:0.5,
                        color: !m.has_key && !m.free_tier ? "#888"
                          : m.free_tier ? "var(--published,#22c55e)"
                          : "var(--approved)"}}>
                        {m.free_tier ? "FREE" : m.has_key ? "LIVE" : "NO KEY"}
                      </span>
                      {isChosen && <span className="tag" style={{fontSize:9, background:"var(--approved)", color:"#fff"}}>DEFAULT</span>}
                      {m.arena_rank && <span className="mono" style={{fontSize:10, opacity:0.7}}>#{m.arena_rank} arena</span>}
                    </div>
                    <div>
                      <div style={{fontWeight:600}}>{m.name}</div>
                      <div className="mono" style={{fontSize:11, opacity:0.7, marginTop:2}}>
                        {m.id} · {m.provider}
                        {m.est_usd !== null && m.est_usd > 0 && <> · ~${m.est_usd.toFixed(3)}/use</>}
                        {m.est_usd === 0 && <> · $0</>}
                      </div>
                      {m.best_for && <div className="note" style={{fontSize:12, marginTop:2}}>{m.best_for}</div>}
                      {m.key_env && <div className="mono" style={{fontSize:10, opacity:0.6, marginTop:2}}>
                        {m.has_key ? "✓ " : "add env: "}{m.key_env}
                      </div>}
                    </div>
                    <div>
                      <button disabled={!m.has_key && !m.free_tier} onClick={() => setDefault(k, m.id)}>
                        {isChosen ? "✓ active" : "Use this"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      <div style={{marginTop:36, padding:"14px 18px", border:"1px solid var(--line)", borderRadius:10}}>
        <b>How to add a new API key</b>
        <ol style={{margin:"8px 0 0 20px", padding:0, fontSize:13}}>
          <li>Go to Railway → your worker service → Variables</li>
          <li>Add the env var shown next to the model (e.g. <span className="mono">FAL_KEY</span>, <span className="mono">OPENAI_API_KEY</span>, <span className="mono">BFL_API_KEY</span>)</li>
          <li>Redeploy. Agent-X detects it automatically and lights up the "LIVE" badge above.</li>
          <li>Click "Use this" on the model you want as default. Agents pick up the change within 60 seconds — no redeploy.</li>
        </ol>
      </div>
    </div>
  );
}
