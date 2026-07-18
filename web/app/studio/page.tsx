import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import StudioBoard from "@/components/StudioBoard";

export const dynamic = "force-dynamic";
const TENANT = process.env.TENANT_ID || "me";

export default async function Studio() {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user) redirect("/login");
  if (!isAdmin(user.email)) redirect("/dashboard");

  const sb = supabaseAdmin();
  const [{ data: items }, { data: ledger }, { data: killRow }, { data: subs }, usersRes] = await Promise.all([
    sb.from("board_items").select("id,status,topic,payload,created_at").eq("tenant_id", TENANT).order("created_at", { ascending: false }).limit(100),
    sb.from("run_ledger").select("step,cost_usd,ok,created_at").gte("created_at", new Date().toISOString().slice(0, 10)).limit(3000),
    sb.from("settings").select("key,value").eq("tenant_id", TENANT).in("key", ["kill_switch", "digest_latest"]),
    sb.from("task_progress").select("user_id,task_key,proof,updated_at").not("proof", "is", null).order("updated_at", { ascending: false }).limit(50),
    sb.auth.admin.listUsers({ perPage: 500 }),
  ]);
  const emailOf: Record<string, string> = {};
  (usersRes?.data?.users || []).forEach((u: any) => { emailOf[u.id] = u.email || u.id.slice(0, 8); });
  const stepTitle: Record<string, string> = {};
  const { COURSES } = await import("@/lib/courses");
  Object.values(COURSES).forEach((c: any) => c.modules.forEach((m: any) => m.steps.forEach((s: any) => { stepTitle[s.key] = `${c.name.split(" — ")[0]} · ${s.title}`; })));
  const submissions = await Promise.all((subs || []).map(async (r: any) => {
    let shot: string | null = null;
    if (r.proof?.type === "screenshot" && r.proof?.value) {
      const { data: signed } = await sb.storage.from("proofs").createSignedUrl(r.proof.value, 3600);
      shot = signed?.signedUrl || null;
    }
    return { ...r, email: emailOf[r.user_id] || "unknown", title: stepTitle[r.task_key] || r.task_key, shot };
  }));
  const spent = (ledger || []).reduce((a, r) => a + Number(r.cost_usd), 0);
  const agentStats: Record<string, { runs: number; fails: number; cost: number; last: string }> = {};
  (ledger || []).forEach((r: any) => {
    const a = (agentStats[r.step] ||= { runs: 0, fails: 0, cost: 0, last: r.created_at });
    a.runs += 1; if (r.ok === false) a.fails += 1; a.cost += Number(r.cost_usd || 0);
    if (r.created_at > a.last) a.last = r.created_at;
  });
  const AGENT_ORDER = ["strategy", "brain", "critique", "visuals", "voice", "captions", "produce", "publish", "community", "digest"];
  const AGENT_NAMES: Record<string, string> = { strategy: "Strategist", brain: "Writer", critique: "Critic", visuals: "Art dept", voice: "Voice", captions: "Captions", produce: "Renderer", publish: "Publisher", community: "Community", digest: "Analyst" };
  const agents = AGENT_ORDER.filter(k => agentStats[k]).map(k => ({ key: k, name: AGENT_NAMES[k] || k, ...agentStats[k] }));
  const killOn = !!killRow?.find((r: any) => r.key === "kill_switch")?.value?.on;
  const digest = killRow?.find((r: any) => r.key === "digest_latest")?.value;

  return (
    <>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2>Production board</h2>
          <span className="tag mono">spent today: ${spent.toFixed(2)}</span>
        </div>
        <p className="lead">Approve moves a clip to the publish queue. Reject kills it. The stop button halts the worker within one tick.</p>
        {agents.length > 0 && (
          <div className="agents">
            {agents.map(a => (
              <div className="agentchip" key={a.key}>
                <b>{a.name}</b>
                <span>{a.runs} run{a.runs === 1 ? "" : "s"}{a.fails > 0 ? ` · ${a.fails} err` : ""}</span>
                <span>{a.cost > 0 ? `$${a.cost.toFixed(2)}` : "free"} · {new Date(a.last).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
              </div>
            ))}
          </div>
        )}
        <div style={{ marginTop: 24 }}>
          {digest?.md && (
            <div className="card" style={{ marginBottom: 24 }}>
              <p className="eyebrow">Weekly digest — {new Date(digest.at).toLocaleDateString()}</p>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 14, lineHeight: 1.6, margin: 0 }}>{digest.md}</pre>
            </div>
          )}
          <StudioBoard items={(items as any) || []} killOn={killOn} />
          <div style={{ marginTop: 36 }}>
            <h3>Course submissions</h3>
            <p className="note" style={{ marginBottom: 12 }}>Latest verification proofs from students. This is your quality window into who is actually doing the work.</p>
            {submissions.length === 0 ? (
              <div className="honest">No submissions yet. They appear here the moment a student verifies a step.</div>
            ) : (
              <div className="steps">
                {submissions.map((s: any, i: number) => (
                  <div className="step" key={i} style={{ display: "block" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <h4>{s.title}</h4>
                      <span className="note mono">{new Date(s.updated_at).toLocaleString()}</span>
                    </div>
                    <p className="note">{s.email}</p>
                    {s.proof?.type === "link" && <a href={s.proof.value} target="_blank" style={{ color: "var(--scheduled)", fontSize: 14 }}>{s.proof.value}</a>}
                    {s.proof?.type === "text" && <p style={{ fontSize: 14, borderLeft: "2px solid var(--line)", paddingLeft: 10, whiteSpace: "pre-wrap" }}>{s.proof.value}</p>}
                    {s.shot && <a href={s.shot} target="_blank"><img src={s.shot} alt="proof" style={{ maxWidth: 260, borderRadius: 8, border: "1px solid var(--line)", marginTop: 6 }} /></a>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
    </>
  );
}
