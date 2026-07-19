"use client";
import { useEffect, useState } from "react";

type Agent = { slug: string; name: string; tagline: string; description: string; category: string;
  price_usd: number; capabilities: string[]; demo_script: { q: string; a: string }[] };
type Lead = { agent_slug: string; status: string; sale_usd: number | null; commission_usd: number | null;
  commission_paid: boolean; created_at: string };

export default function MarketplacePage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [code, setCode] = useState<string | null>(null);
  const [clicks, setClicks] = useState(0);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [demo, setDemo] = useState<Agent | null>(null);
  const [step, setStep] = useState(0);
  const [copied, setCopied] = useState("");

  useEffect(() => {
    fetch("/api/marketplace").then(r => r.json()).then(j => {
      if (j.agents) { setAgents(j.agents); setCode(j.code); setClicks(j.clicks || 0); setLeads(j.leads || []); }
    });
  }, []);

  function myLink(slug: string) { return `${location.origin}/r/${code}?a=${slug}`; }
  async function copy(slug: string) {
    await navigator.clipboard.writeText(myLink(slug));
    setCopied(slug); setTimeout(() => setCopied(""), 1500);
  }
  const owed = leads.filter(l => l.status === "closed_won" && !l.commission_paid)
    .reduce((s, l) => s + Number(l.commission_usd || 0), 0);
  const paid = leads.filter(l => l.commission_paid).reduce((s, l) => s + Number(l.commission_usd || 0), 0);

  return (
    <div>
      <h1>Agent marketplace</h1>
      <p className="lead">
        Sell Agent-X business agents to companies and keep <b>50% of every sale</b> you refer.
        Share your link anywhere; when a company you sent signs up, half the deal is yours.
      </p>

      {code && (
        <div className="card" style={{ marginBottom: 24, display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
          <div><span className="note">Your code</span><br /><b style={{ fontSize: 18 }}>{code}</b></div>
          <div><span className="note">Link clicks</span><br /><b style={{ fontSize: 18 }}>{clicks}</b></div>
          <div><span className="note">Leads</span><br /><b style={{ fontSize: 18 }}>{leads.length}</b></div>
          <div><span className="note">Commission owed</span><br /><b style={{ fontSize: 18, color: "var(--approved)" }}>${owed.toFixed(2)}</b></div>
          <div><span className="note">Paid out</span><br /><b style={{ fontSize: 18 }}>${paid.toFixed(2)}</b></div>
        </div>
      )}

      <div className="grid3">
        {agents.map(a => (
          <div key={a.slug} className="card">
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <h3 style={{ margin: 0 }}>{a.name}</h3>
              <span className="tag">{a.category}</span>
            </div>
            <p className="note" style={{ margin: "6px 0 10px" }}>{a.tagline}</p>
            <p style={{ fontSize: 14 }}>{a.description}</p>
            <ul style={{ fontSize: 13, paddingLeft: 18, color: "var(--muted)" }}>
              {(a.capabilities || []).map(c => <li key={c}>{c}</li>)}
            </ul>
            <p style={{ fontSize: 20, margin: "8px 0" }}>${a.price_usd}<span className="note">/mo</span>
              <span className="note" style={{ marginLeft: 10 }}>→ you earn ${(a.price_usd / 2).toFixed(0)}/sale</span></p>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => copy(a.slug)} disabled={!code}>
                {copied === a.slug ? "Copied!" : "Get my 50% link"}
              </button>
              <button onClick={() => { setDemo(a); setStep(0); }}
                style={{ background: "none", border: "1px solid var(--line)" }}>Try demo</button>
            </div>
          </div>
        ))}
        {agents.length === 0 && <p className="note">Loading catalog… (run db/v1.6.sql if this never loads)</p>}
      </div>

      {leads.length > 0 && (
        <div className="card" style={{ marginTop: 32 }}>
          <h3>Your referred leads</h3>
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead><tr className="note"><th align="left">Agent</th><th align="left">Status</th><th align="right">Sale</th><th align="right">Your 50%</th><th align="left">Paid</th></tr></thead>
            <tbody>{leads.map((l, i) => (
              <tr key={i}>
                <td>{l.agent_slug}</td><td>{l.status.replace("_", " ")}</td>
                <td align="right">{l.sale_usd ? "$" + l.sale_usd : "—"}</td>
                <td align="right">{l.commission_usd ? "$" + l.commission_usd : "—"}</td>
                <td>{l.commission_paid ? "✓" : ""}</td>
              </tr>))}
            </tbody>
          </table>
        </div>
      )}

      {demo && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.7)", display: "grid", placeItems: "center", zIndex: 50 }}
          onClick={() => setDemo(null)}>
          <div className="card" style={{ maxWidth: 460, width: "92%" }} onClick={e => e.stopPropagation()}>
            <h3>{demo.name}</h3>
            <p className="note">Scripted demo preview — live pilots run on <i>your</i> data during onboarding.</p>
            {(demo.demo_script || []).slice(0, step + 1).map((d, i) => (
              <div key={i} style={{ margin: "10px 0" }}>
                <p style={{ fontSize: 13, color: "var(--muted)" }}>Customer: {d.q}</p>
                <p style={{ fontSize: 14, background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: 10 }}>{d.a}</p>
              </div>
            ))}
            <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
              {step + 1 < (demo.demo_script || []).length &&
                <button onClick={() => setStep(step + 1)}>Next exchange →</button>}
              <button onClick={() => setDemo(null)} style={{ background: "none", border: "1px solid var(--line)" }}>Close</button>
            </div>
          </div>
        </div>
      )}

      <p className="note" style={{ marginTop: 28 }}>
        How payouts work: when a company you referred signs, the sale is marked <b>closed&nbsp;won</b> and
        50% is credited as commission owed to you, then paid out to your wallet. Sales are closed by a
        human — agents never sign contracts on their own.
      </p>
    </div>
  );
}
