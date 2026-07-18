"use client";
import { useEffect, useState } from "react";

type WalletData = {
  balance: number;
  spent: number;
  topup: number;
  tx: { id: number; type: string; amount: number; note: string | null; step: string | null; created_at: string }[];
  error?: string;
};

const PACKS = [
  { usd: 5, credits: 5, bonus: 0, label: "Starter" },
  { usd: 15, credits: 18, bonus: 3, label: "Creator" },
  { usd: 30, credits: 39, bonus: 9, label: "Studio" },
  { usd: 75, credits: 105, bonus: 30, label: "Agency", popular: true },
];

const COSTS: [string, number, string][] = [
  ["1 script (hook + beats + critique)", 0.015, "brain"],
  ["4 AI images (Gemini)", 0.04 * 4, "visuals"],
  ["1 minute voiceover", 0.02, "voice"],
  ["Video composition + captions", 0.005, "produce"],
  ["Captions per platform", 0.008, "captions"],
  ["Community reply", 0.006, "community"],
];

export default function WalletPage() {
  const [d, setD] = useState<WalletData | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  async function load() {
    const r = await fetch("/api/wallet", { cache: "no-store" });
    if (r.ok) setD(await r.json());
  }
  useEffect(() => { load(); }, []);

  async function buy(usd: number) {
    setBusy(String(usd)); setMsg("");
    const r = await fetch("/api/wallet/topup", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usd }),
    });
    setBusy(null);
    const j = await r.json().catch(() => ({}));
    if (r.ok && j.url) window.location.href = j.url;
    else if (j.ok) { setMsg("Demo bonus applied."); load(); }
    else setMsg(j.error || "Checkout failed.");
  }

  if (!d) return <p className="note">Loading wallet…</p>;

  const dailyBudget = 3.0;
  const spentPct = Math.min(100, (d.spent / dailyBudget) * 100);

  return (
    <div>
      <h1>Wallet</h1>
      <p className="lead">Pay-as-you-go. One credit = ~1 video. Spend only on content you approve.</p>

      <div className="grid">
        <div className="card" style={{ gridColumn: "span 2" }}>
          <p className="note">Current balance</p>
          <h1 style={{ margin: 0, fontSize: 56 }}>${(d.balance || 0).toFixed(2)}</h1>
          <p className="note">Lifetime spent: ${(d.spent || 0).toFixed(2)} · Lifetime deposits: ${(d.topup || 0).toFixed(2)}</p>
          <div style={{ marginTop: 14 }}>
            <p className="note" style={{ fontSize: 12, marginBottom: 4 }}>Today: ${d.spent.toFixed(2)} / ${dailyBudget.toFixed(2)}</p>
            <div style={{ height: 8, background: "var(--line)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ width: `${spentPct}%`, height: "100%", background: spentPct > 80 ? "#e5484d" : "var(--approved)", transition: "width .4s" }} />
            </div>
          </div>
        </div>
        <div className="card">
          <h3>What it costs</h3>
          <p className="note" style={{ fontSize: 12 }}>All priced per use. Free fallback engines (Gemini, Llama) don't charge your wallet.</p>
          <ul style={{ padding: "8px 0 0 18px", margin: 0, fontSize: 13, lineHeight: 1.7 }}>
            {COSTS.map(([l, c]) => (
              <li key={l}>{l} — <span className="mono">${c.toFixed(3)}</span></li>
            ))}
          </ul>
          <p className="note" style={{ marginTop: 10, fontSize: 12 }}>Avg cost per fully-produced approved video: <b>~$0.20</b>.</p>
        </div>
      </div>

      <h2 style={{ marginTop: 32 }}>Add credits</h2>
      <div className="grid">
        {PACKS.map((p) => (
          <div key={p.usd} className="card" style={p.popular ? { borderColor: "var(--draft)" } : undefined}>
            {p.popular && <span className="tag" style={{ color: "var(--draft)" }}>most popular</span>}
            <h3>{p.label}</h3>
            <p style={{ fontSize: 32, margin: "8px 0" }}>${p.usd}</p>
            <p className="note">{p.credits} credits{p.bonus > 0 ? ` + ${p.bonus} free` : ""}{/* ~{Math.round(p.credits / 0.2)} videos */}</p>
            <button className="primary" disabled={busy === String(p.usd)} onClick={() => buy(p.usd)}>
              {busy === String(p.usd) ? "Redirecting…" : "Buy credits"}
            </button>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 32 }}>Transactions</h2>
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        {(d.tx || []).length === 0 && <div className="honest" style={{ padding: 20 }}>No transactions yet.</div>}
        {(d.tx || []).map((t) => (
          <div key={t.id} style={{ display: "flex", gap: 10, padding: "10px 16px", borderBottom: "1px solid var(--line)", fontSize: 13 }}>
            <span className="mono" style={{ color: "var(--dim)", width: 120 }}>{new Date(t.created_at).toLocaleString()}</span>
            <span style={{
              color: t.type === "consume" ? "#e5484d" : t.type === "deposit" || t.type === "bonus" ? "var(--published)" : "var(--scheduled)",
              textTransform: "uppercase",
              width: 70,
              fontSize: 11,
              fontWeight: 600,
              paddingTop: 2,
            }}>{t.type}</span>
            <span style={{ flex: 1 }}>{t.note || t.step || ""}</span>
            <span className="mono">${Number(t.amount).toFixed(2)}</span>
          </div>
        ))}
      </div>
      {msg && <p className="note" style={{ marginTop: 10 }}>{msg}</p>}
    </div>
  );
}
