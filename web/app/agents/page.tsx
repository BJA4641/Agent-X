"use client";
import { useEffect, useState } from "react";

type Agent = { slug: string; name: string; tagline: string; description: string; category: string;
  price_usd: number; capabilities: string[]; demo_script: { q: string; a: string }[] };

export default function AgentsLanding() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [sel, setSel] = useState<string>("");
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "", website: "" });
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState("");
  const [demo, setDemo] = useState<Agent | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    fetch("/api/marketplace?public=1").then(r => r.json()).then(j => {
      setAgents(j.agents || []);
      const a = new URLSearchParams(location.search).get("a");
      if (a) setSel(a);
    });
  }, []);

  async function submit() {
    setErr("");
    const r = await fetch("/api/agent-leads", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...form, agent_slug: sel || (agents[0]?.slug ?? "") }),
    });
    const j = await r.json();
    if (!r.ok) { setErr(j.error || "Failed"); return; }
    setSent(true);
  }

  return (
    <main style={{ maxWidth: 1080, margin: "0 auto", padding: "48px 20px" }}>
      <h1 style={{ fontSize: 34 }}>AI agents that do real work for your business</h1>
      <p className="lead" style={{ maxWidth: 640 }}>
        Each Agent-X agent is set up on <b>your</b> data during a guided onboarding, works inside
        clear guardrails, and escalates to humans when unsure. Fixed monthly price. Cancel anytime.
      </p>

      <div className="grid3" style={{ marginTop: 36 }}>
        {agents.map(a => (
          <div key={a.slug} className="card" style={{ borderColor: sel === a.slug ? "var(--approved)" : undefined }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <h3 style={{ margin: 0 }}>{a.name}</h3><span className="tag">{a.category}</span>
            </div>
            <p className="note" style={{ margin: "6px 0 10px" }}>{a.tagline}</p>
            <ul style={{ fontSize: 13, paddingLeft: 18, color: "var(--muted)" }}>
              {(a.capabilities || []).slice(0, 4).map(c => <li key={c}>{c}</li>)}
            </ul>
            <p style={{ fontSize: 20 }}>${a.price_usd}<span className="note">/mo</span></p>
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={() => { setSel(a.slug); document.getElementById("lead")?.scrollIntoView({ behavior: "smooth" }); }}>
                Talk to us
              </button>
              <button onClick={() => { setDemo(a); setStep(0); }} style={{ background: "none", border: "1px solid var(--line)" }}>
                Preview
              </button>
            </div>
          </div>
        ))}
      </div>

      <div id="lead" className="card" style={{ marginTop: 48, maxWidth: 520 }}>
        <h3>Book a pilot{sel ? ` — ${agents.find(a => a.slug === sel)?.name?.split(" — ")[0] || sel}` : ""}</h3>
        {sent ? <p style={{ color: "var(--approved)" }}>Thanks — we reply within one business day.</p> : (<>
          <p className="note">Tell us a little about the job. A human replies — no automated sales calls.</p>
          {err && <p className="note" style={{ color: "var(--failed)" }}>{err}</p>}
          <div style={{ display: "grid", gap: 10, marginTop: 10 }}>
            <select value={sel} onChange={e => setSel(e.target.value)} style={inp}>
              <option value="">Which agent?</option>
              {agents.map(a => <option key={a.slug} value={a.slug}>{a.name}</option>)}
            </select>
            <input placeholder="Your name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} style={inp} />
            <input placeholder="Work email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} style={inp} />
            <input placeholder="Company (optional)" value={form.company} onChange={e => setForm({ ...form, company: e.target.value })} style={inp} />
            <textarea placeholder="What should the agent handle?" rows={3} value={form.message}
              onChange={e => setForm({ ...form, message: e.target.value })} style={inp} />
            <input style={{ display: "none" }} tabIndex={-1} autoComplete="off" value={form.website}
              onChange={e => setForm({ ...form, website: e.target.value })} />
            <button onClick={submit}>Request pilot</button>
          </div>
        </>)}
      </div>

      {demo && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.7)", display: "grid", placeItems: "center", zIndex: 50 }}
          onClick={() => setDemo(null)}>
          <div className="card" style={{ maxWidth: 460, width: "92%" }} onClick={e => e.stopPropagation()}>
            <h3>{demo.name}</h3>
            <p className="note">Scripted preview — your live pilot runs on your own data.</p>
            {(demo.demo_script || []).slice(0, step + 1).map((d, i) => (
              <div key={i} style={{ margin: "10px 0" }}>
                <p style={{ fontSize: 13, color: "var(--muted)" }}>Customer: {d.q}</p>
                <p style={{ fontSize: 14, background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: 10 }}>{d.a}</p>
              </div>
            ))}
            <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
              {step + 1 < (demo.demo_script || []).length && <button onClick={() => setStep(step + 1)}>Next →</button>}
              <button onClick={() => setDemo(null)} style={{ background: "none", border: "1px solid var(--line)" }}>Close</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
const inp = { background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" } as const;
