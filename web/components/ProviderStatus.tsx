"use client";

/* v5.8.7 — "which AI modules are linked, which are live, how much credit is left"
   Data comes from settings.provider_status, written by the worker's
   providers.probe job (Railway env = ground truth, not Vercel's env).

   Honesty rule: a balance is shown ONLY when the vendor actually exposes a
   balance endpoint and returned a number. Everyone else says so plainly
   instead of showing a fake or blank figure. */

type Rec = {
  provider: string; linked: boolean; status: string;
  balance: number | null; unit: string | null;
  role?: string; note?: string; spend_today_usd?: number; http?: number;
};

const CHIP: Record<string, { bg: string; fg: string; label: string }> = {
  ok:            { bg: "rgba(34,197,94,.14)",  fg: "#22c55e", label: "LIVE" },
  linked:        { bg: "rgba(59,130,246,.14)", fg: "#60a5fa", label: "LINKED" },
  no_key:        { bg: "rgba(107,114,128,.16)",fg: "#9ca3af", label: "NOT CONNECTED" },
  out_of_credit: { bg: "rgba(239,68,68,.14)",  fg: "#ef4444", label: "OUT OF CREDIT" },
  dead_key:      { bg: "rgba(239,68,68,.14)",  fg: "#ef4444", label: "BAD KEY" },
  rate_limited:  { bg: "rgba(245,158,11,.14)", fg: "#f59e0b", label: "RATE LIMITED" },
  unreachable:   { bg: "rgba(245,158,11,.14)", fg: "#f59e0b", label: "UNREACHABLE" },
};

function chip(status: string) {
  return CHIP[status] || { bg: "rgba(245,158,11,.14)", fg: "#f59e0b", label: status.toUpperCase() };
}

function money(r: Rec) {
  if (r.balance === null || r.balance === undefined) return null;
  if (r.unit === "USD") return `$${Number(r.balance).toFixed(2)}`;
  if (r.unit === "characters") return `${Math.round(Number(r.balance)).toLocaleString()} chars`;
  return `${r.balance} ${r.unit || ""}`.trim();
}

export default function ProviderStatus({ status, costMode }: { status: any; costMode?: any }) {
  if (!status?.providers) {
    return (
      <div className="card" style={{ padding: 16, marginBottom: 20 }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>🔌 Connected AI modules</h3>
        <p className="note" style={{ marginTop: 8 }}>
          No probe has run yet. The worker checks every provider on boot and every 6 hours —
          this fills in within a minute of a deploy.
        </p>
      </div>
    );
  }

  const recs: Rec[] = Object.values(status.providers);
  const inUse   = recs.filter(r => r.linked && r.status === "ok");
  const problem = recs.filter(r => r.linked && r.status !== "ok");
  const absent  = recs.filter(r => !r.linked);
  const checked = status.checked_at ? new Date(status.checked_at * 1000) : null;
  const free    = (costMode?.mode || status.cost_mode) === "free_only";

  const Row = ({ r }: { r: Rec }) => {
    const c = chip(r.status === "linked" && r.balance === null ? "linked" : r.status);
    const bal = money(r);
    return (
      <div style={{
        display: "grid", gridTemplateColumns: "130px 110px 1fr auto", gap: 10,
        alignItems: "center", padding: "8px 10px", borderRadius: 6,
        background: "rgba(255,255,255,.03)", marginBottom: 6, fontSize: 12.5,
      }}>
        <b style={{ fontFamily: "var(--font-mono)" }}>{r.provider}</b>
        <span style={{
          background: c.bg, color: c.fg, borderRadius: 4, padding: "2px 7px",
          fontSize: 10.5, fontWeight: 700, textAlign: "center", letterSpacing: ".04em",
        }}>{c.label}</span>
        <span style={{ opacity: .8 }}>
          {r.role || "—"}
          {r.note && <span style={{ opacity: .55 }}> · {r.note}</span>}
        </span>
        <span style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
          {bal
            ? <b style={{ color: Number(r.balance) <= 0 ? "#ef4444" : "#22c55e" }}>{bal}</b>
            : <span style={{ opacity: .45 }} title="This vendor has no balance API — check their dashboard">
                no balance API
              </span>}
          {!!r.spend_today_usd &&
            <div style={{ opacity: .55, fontSize: 11 }}>spent today ${r.spend_today_usd.toFixed(3)}</div>}
        </span>
      </div>
    );
  };

  return (
    <div className="card" style={{ padding: 16, marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>🔌 Connected AI modules</h3>
        <span className="note" style={{ fontSize: 11.5 }}>
          {inUse.length} live · {problem.length} need attention · {absent.length} not connected
          {checked && ` · checked ${checked.toLocaleTimeString()}`}
        </span>
        {free && <span style={{
          marginLeft: "auto", color: "#22c55e", border: "1px solid #22c55e",
          borderRadius: 4, padding: "1px 8px", fontSize: 11,
        }}>FREE-ONLY MODE — paid calls suspended</span>}
      </div>

      <p className="note" style={{ fontSize: 11.5, margin: "8px 0 12px" }}>
        Status is read from the <b>worker&apos;s</b> environment on Railway — the machine that
        actually spends the money. Balances appear only for vendors that publish a balance
        endpoint (OpenRouter, DeepSeek, ElevenLabs, Stability). The rest can be validated but
        must be topped up from their own dashboards.
      </p>

      {problem.length > 0 && (<>
        <h4 style={{ fontSize: 12, opacity: .7, margin: "10px 0 6px" }}>NEEDS ATTENTION</h4>
        {problem.map(r => <Row key={r.provider} r={r} />)}
      </>)}

      <h4 style={{ fontSize: 12, opacity: .7, margin: "10px 0 6px" }}>LIVE</h4>
      {inUse.length ? inUse.map(r => <Row key={r.provider} r={r} />)
                    : <p className="note">Nothing is live yet.</p>}

      {absent.length > 0 && (<>
        <h4 style={{ fontSize: 12, opacity: .7, margin: "14px 0 6px" }}>
          NOT CONNECTED — add the key in Railway to enable
        </h4>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {absent.map(r => (
            <span key={r.provider} title={r.role}
              style={{ fontSize: 11.5, fontFamily: "var(--font-mono)", opacity: .6,
                border: "1px dashed #4b5563", borderRadius: 4, padding: "2px 8px" }}>
              {r.provider}
            </span>
          ))}
        </div>
      </>)}
    </div>
  );
}
