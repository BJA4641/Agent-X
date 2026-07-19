"use client";
import { useEffect, useState } from "react";

type Provider = {
  id: string;
  name: string;
  key_present: boolean;
  active: boolean;
  status: "ok" | "warn" | "error" | "missing";
  balance_usd?: number | null;
  balance_note?: string;
  usage_mtd_usd?: number;
  last_call_at?: string | null;
  free_tier?: boolean;
};

function timeAgo(iso?: string | null): string {
  if (!iso) return "never used";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const STATUS_COLOR: Record<string, string> = {
  ok: "var(--published, #22c55e)",
  warn: "#f59e0b",
  error: "#ef4444",
  missing: "#6b7280",
};
const STATUS_LABEL: Record<string, string> = {
  ok: "LIVE", warn: "WARNING", error: "ERROR", missing: "NO KEY",
};

export default function ProviderBalances() {
  const [data, setData] = useState<{ providers: Provider[]; checked_at: string; active_provider: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const refresh = async () => {
    setLoading(true); setErr("");
    try {
      const r = await fetch("/api/providers/balance", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || "Failed");
      setData(j);
    } catch (e: any) {
      setErr(e.message || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <div style={{ marginTop: 36 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>AI provider wallets</h2>
        <span className="tag" style={{ background: "var(--card,#222)", color: "var(--muted,#aaa)" }}>
          live balance check
        </span>
        <button onClick={refresh} style={{ marginLeft: "auto" }} disabled={loading}>
          {loading ? "Checking…" : "↻ Refresh"}
        </button>
      </div>
      <p className="note" style={{ maxWidth: 720, marginTop: 0 }}>
        Live status of every AI &amp; hosting wallet connected to Agent-X. When one provider runs out of credits
        or fails, the agents <b>automatically fall back</b> to the next working provider so production never stops.
        Paid balances (like your Anthropic credits) are shown here when the provider&apos;s API allows it; free tiers
        are labeled FREE.
      </p>
      {err && <p className="note" style={{ color: "#ef4444" }}>{err}</p>}
      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        {(data?.providers || []).map((p) => (
          <div key={p.id} className="card" style={{
            padding: 14, display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 12, alignItems: "center",
            borderLeft: `4px solid ${STATUS_COLOR[p.status]}`,
          }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 70 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: STATUS_COLOR[p.status], letterSpacing: 0.5 }}>
                {STATUS_LABEL[p.status]}
              </span>
              {p.active && <span className="tag" style={{ marginTop: 4, fontSize: 10, background: "var(--published,#22c55e)", color: "#fff" }}>ACTIVE</span>}
              {p.free_tier && <span className="tag" style={{ marginTop: 4, fontSize: 10 }}>FREE</span>}
            </div>
            <div>
              <div style={{ fontWeight: 600 }}>{p.name}</div>
              <div className="note" style={{ fontSize: 12, marginTop: 2 }}>{p.balance_note}</div>
              <div className="mono" style={{ fontSize: 11, marginTop: 4, opacity: 0.7 }}>
                MTD spend: ${(p.usage_mtd_usd || 0).toFixed(3)} · last call: {timeAgo(p.last_call_at)}
              </div>
            </div>
            <div style={{ textAlign: "right", minWidth: 90 }}>
              {p.balance_usd !== null && p.balance_usd !== undefined ? (
                <div style={{ fontSize: 20, fontWeight: 700 }}>${p.balance_usd.toFixed(2)}</div>
              ) : (
                <div className="note" style={{ fontSize: 12 }}>
                  {p.free_tier ? "unlimited" : "see provider console"}
                </div>
              )}
              {p.free_tier && <div className="note" style={{ fontSize: 10 }}>free tier</div>}
            </div>
          </div>
        ))}
        {!data && !loading && !err && <p className="note">No data.</p>}
      </div>
      {data?.checked_at && (
        <p className="mono" style={{ fontSize: 11, opacity: 0.6, marginTop: 10 }}>
          Last check: {new Date(data.checked_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}
