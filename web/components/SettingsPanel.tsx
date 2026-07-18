"use client";
import { useState } from "react";

const PROVIDERS = [
  { id: "anthropic", name: "Claude Sonnet (Anthropic)", cost: "~$0.01–0.03 per video", note: "Highest quality scripts and critiques. Uses your Anthropic key.", free: false },
  { id: "gemini", name: "Gemini 2.5 Flash (Google)", cost: "FREE tier", note: "Very good. Uses the same GEMINI_API_KEY already powering your images — works today, no new key.", free: true },
  { id: "openrouter", name: "Kimi K2 (via OpenRouter)", cost: "FREE", note: "Strong open model. Needs OPENROUTER_API_KEY in Railway (openrouter.ai → free signup).", free: true },
  { id: "groq", name: "Llama 3.3 70B (Groq)", cost: "FREE tier", note: "Fastest option. Needs GROQ_API_KEY in Railway (console.groq.com → free signup).", free: true },
];

export default function SettingsPanel({ isAdmin, initialProvider, initialModel, initialBudget, spentToday }:
  { isAdmin: boolean; initialProvider: string; initialModel: string; initialBudget: number; spentToday: number }) {
  const [provider, setProvider] = useState(initialProvider);
  const [model, setModel] = useState(initialModel);
  const [budget, setBudget] = useState(initialBudget);
  const [msg, setMsg] = useState("");

  if (!isAdmin) return (
    <p className="note" style={{ marginTop: 24 }}>AI engine and budget controls are managed by the workspace owner.</p>
  );

  const post = async (payload: any, ok: string) => {
    setMsg("Saving…");
    const r = await fetch("/api/studio", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const j = await r.json();
    setMsg(r.ok ? ok : (j.error || "Failed"));
  };

  return (
    <>
      <h2 style={{ marginTop: 32 }}>AI engine</h2>
      <p className="note" style={{ maxWidth: 640 }}>
        Which model writes your scripts, critiques, captions, and strategy. Takes effect within a minute — no redeploy.
        If the chosen model&apos;s key is missing or it fails, the factory automatically falls back to whatever key it has, so
        production never stops.
      </p>
      <div className="grid" style={{ marginTop: 12 }}>
        {PROVIDERS.map((p) => (
          <label key={p.id} className="card" style={{ cursor: "pointer", borderColor: provider === p.id ? "var(--approved)" : undefined }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input type="radio" name="provider" checked={provider === p.id} onChange={() => setProvider(p.id)} />
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              <span className="tag" style={{ marginLeft: "auto", color: p.free ? "var(--published)" : undefined }}>{p.cost}</span>
            </div>
            <p className="note" style={{ marginTop: 8 }}>{p.note}</p>
          </label>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
        <input className="mono" placeholder="custom model id (optional)" value={model} onChange={(e) => setModel(e.target.value)}
               style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px", color: "inherit", minWidth: 260 }} />
        <button onClick={() => post({ action: "set_model", provider, model }, "Engine saved ✓ — active within a minute")}>Save engine</button>
      </div>

      <h2 style={{ marginTop: 32 }}>Daily spend limit</h2>
      <p className="note" style={{ maxWidth: 640 }}>
        Hard cap on paid AI spend per day. When it&apos;s reached, every agent switches to its free fallback until midnight —
        the factory keeps running, it just stops spending. Free-tier engines don&apos;t count against this.
      </p>
      <p className="mono" style={{ fontSize: 13 }}>Spent today: ${spentToday.toFixed(3)}</p>
      <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
        <span>$</span>
        <input type="number" min={0} max={100} step={0.5} value={budget} onChange={(e) => setBudget(Number(e.target.value))}
               style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 12px", color: "inherit", width: 100 }} />
        <span className="note">per day</span>
        <button onClick={() => post({ action: "set_budget", usd: budget }, "Budget saved ✓")}>Save limit</button>
      </div>
      {msg && <p className="note" style={{ marginTop: 10 }}>{msg}</p>}
    </>
  );
}
