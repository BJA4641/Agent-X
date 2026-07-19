import Link from "next/link";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

export default async function RightPanel() {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();

  // Pending approvals (board_items in 'drafted' state awaiting review)
  let pending: any[] = [];
  let events: any[] = [];
  let balance = 0;
  let spentToday = 0;
  let todoCount = 0;

  try {
    const [{ data: p }, { data: e }, { data: w }, { data: l }] = await Promise.all([
      admin.from("board_items").select("id,topic,status,created_at")
        .eq("status", "drafted").order("created_at", { ascending: false }).limit(5),
      admin.from("agent_events").select("agent,action,message,status,created_at,cost_usd")
        .order("created_at", { ascending: false }).limit(8),
      admin.from("wallets").select("balance_usd").eq("user_id", user!.id).maybeSingle(),
      admin.from("run_ledger").select("cost_usd,created_at").gte("created_at", new Date(new Date().setHours(0,0,0,0)).toISOString()),
    ]);
    pending = p || [];
    events = e || [];
    balance = Number(w?.balance_usd || 0);
    spentToday = (l || []).reduce((a: number, r: any) => a + Number(r.cost_usd || 0), 0);
  } catch {
    // tables may not exist yet
  }

  // Next tasks (static to-do until we compute from progress)
  const todos = [
    { label: "Finish workspace setup", href: "/dashboard/onboarding", done: false },
    { label: "Connect first social account", href: "/dashboard/settings", done: false },
    { label: "Add $5 credits (demo mode)", href: "/dashboard/wallet", done: balance >= 5 },
    { label: "Open your first track", href: "/dashboard", done: false },
  ];
  const openTodos = todos.filter(t => !t.done);

  const agentColor: Record<string,string> = {
    brain: "var(--draft)", visuals: "var(--scheduled)", voice: "var(--approved)",
    qa: "var(--failed)", strategy: "#a78bfa", planner: "#60a5fa", publish: "#34d399",
    system: "var(--dim)",
  };

  return (
    <aside style={{ borderLeft: "1px solid var(--line)", padding: "20px 0 20px 20px", display: "flex", flexDirection: "column", gap: 24, fontSize: 13 }}>
      {/* Wallet card */}
      <div className="card" style={{ margin: 0, background: "linear-gradient(135deg, rgba(16,185,129,0.08), rgba(59,130,246,0.08))" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <b>Wallet</b>
          <span className="tag">live</span>
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, margin: "6px 0 2px" }}>${balance.toFixed(2)}</div>
        <div className="note" style={{ margin: "0 0 10px" }}>Spent today: ${spentToday.toFixed(3)}</div>
        <Link href="/dashboard/wallet" style={{ fontSize: 12, color: "var(--scheduled)" }}>Top up / history →</Link>
      </div>

      {/* To-do */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
          <h5 style={{ margin: 0, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, color: "var(--dim)" }}>Next tasks</h5>
          <span className="tag">{openTodos.length} open</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {todos.map(t => (
            <Link key={t.label} href={t.href} style={{
              padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 8,
              textDecoration: "none", color: "inherit", display: "flex", alignItems: "center", gap: 8,
              background: t.done ? "rgba(16,185,129,0.08)" : undefined,
            }}>
              <span style={{
                width: 14, height: 14, borderRadius: 4, border: "1.5px solid " + (t.done ? "var(--approved)" : "var(--line)"),
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                background: t.done ? "var(--approved)" : "transparent", fontSize: 10, color: "#fff", flexShrink: 0,
              }}>{t.done ? "✓" : ""}</span>
              <span style={{ fontSize: 13, textDecoration: t.done ? "line-through" : "none", opacity: t.done ? 0.6 : 1 }}>{t.label}</span>
            </Link>
          ))}
        </div>
      </div>

      {/* Pending approval */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
          <h5 style={{ margin: 0, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, color: "var(--dim)" }}>Awaiting your approval</h5>
          <span className="tag">{pending.length}</span>
        </div>
        {pending.length === 0 ? (
          <p className="note" style={{ margin: 0, fontSize: 12 }}>Nothing in your queue yet. Run the Studio or Clone Viral to generate drafts.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {pending.map((item) => (
              <Link key={item.id} href="/studio" style={{
                padding: "8px 10px", border: "1px solid var(--draft)", borderRadius: 8,
                textDecoration: "none", color: "inherit",
              }}>
                <div style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.topic}</div>
                <div className="note" style={{ fontSize: 11, margin: 0 }}>drafted · {timeAgo(item.created_at)}</div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Agent feed */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
          <h5 style={{ margin: 0, fontSize: 12, textTransform: "uppercase", letterSpacing: 1, color: "var(--dim)" }}>Agent activity</h5>
          <Link href="/dashboard/workspace" className="tag" style={{ textDecoration: "none", fontSize: 11 }}>open feed →</Link>
        </div>
        {events.length === 0 ? (
          <div style={{ padding: 10, border: "1px dashed var(--line)", borderRadius: 8 }}>
            <p className="note" style={{ margin: 0, fontSize: 12 }}>
              Agents are idle. Queue topics from <Link href="/studio" style={{ color: "var(--scheduled)" }}>Studio</Link> to wake them up.
            </p>
            <p className="note" style={{ margin: "6px 0 0", fontSize: 11, opacity: 0.7 }}>Pipeline worker starts producing once topics are in 'idea' state.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {events.slice(0,6).map((ev, i) => (
              <div key={i} style={{ fontSize: 12, display: "flex", gap: 8, alignItems: "flex-start", padding: "4px 0", borderBottom: "1px solid var(--line)" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: agentColor[ev.agent] || "var(--dim)", marginTop: 4, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 6 }}>
                    <b style={{ fontSize: 11, textTransform: "capitalize" }}>{ev.agent}</b>
                    <span className="note" style={{ fontSize: 10 }}>{timeAgo(ev.created_at)}</span>
                  </div>
                  <div className="note" style={{ fontSize: 11, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ev.message || ev.action}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
