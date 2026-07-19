import Link from "next/link";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function PerformancePage() {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;

  const today = new Date(); today.setHours(0,0,0,0);
  let perf: any[] = [], ledger: any[] = [], items: any[] = [];
  try { const r = await admin.from("performance").select("*").order("captured_at",{ascending:false}).limit(50); perf = r.data || []; } catch {}
  try { const r = await admin.from("run_ledger").select("step,ok,cost_usd,created_at").gte("created_at", today.toISOString()); ledger = r.data || []; } catch {}
  try { const r = await admin.from("board_items").select("id,status,topic,created_at").eq("tenant_id","me").order("created_at",{ascending:false}).limit(20); items = r.data || []; } catch {}

  const totalRuns = ledger.length;
  const fails = ledger.filter(r => r.ok === false).length;
  const spend = ledger.reduce((a:number,r:any)=>a+Number(r.cost_usd||0),0);
  const published = items.filter(i=>i.status==='published').length;
  const drafted = items.filter(i=>i.status==='drafted').length;
  const approved = items.filter(i=>i.status==='approved').length;

  const byAgent: Record<string,{runs:number,fails:number,cost:number}> = {};
  ledger.forEach((r:any)=>{
    const a = (byAgent[r.step] ||= {runs:0,fails:0,cost:0});
    a.runs++; if(!r.ok)a.fails++; a.cost+=Number(r.cost_usd||0);
  });

  return (
    <div>
      <h1>Performance</h1>
      <p className="lead">Track how your agents, content, and income are performing across projects.</p>

      <div className="grid3" style={{marginTop:24}}>
        <div className="card">
          <p className="note">Content produced today</p>
          <h2 style={{margin:"4px 0"}}>{totalRuns} steps</h2>
          <p className="note">{drafted} drafted · {approved} approved · {published} published · {fails} errors</p>
        </div>
        <div className="card">
          <p className="note">Spend today</p>
          <h2 style={{margin:"4px 0"}}>${spend.toFixed(3)}</h2>
          <p className="note">Pipeline cost (before markup)</p>
        </div>
        <div className="card">
          <p className="note">Total views</p>
          <h2 style={{margin:"4px 0"}}>
            {perf.reduce((a:number,r:any)=>a+Number(r.views||0),0).toLocaleString()}
          </h2>
          <p className="note">Across connected platforms (live once accounts linked)</p>
        </div>
      </div>

      <h2 style={{marginTop:36}}>Agent breakdown (today)</h2>
      {Object.keys(byAgent).length === 0 ? (
        <div className="honest">No agent runs yet. Queue a topic from <Link href="/studio" style={{color:"var(--scheduled)"}}>Studio</Link> or <Link href="/dashboard/clone" style={{color:"var(--scheduled)"}}>Clone viral</Link> to wake the agents.</div>
      ) : (
        <div className="steps" style={{marginTop:12}}>
          {Object.entries(byAgent).map(([name,stats])=>(
            <div key={name} className="step" style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <div>
                <h4 style={{textTransform:"capitalize",margin:0}}>{name}</h4>
                <p className="note" style={{margin:0}}>{stats.runs} runs{stats.fails?` · ${stats.fails} failed`:""}</p>
              </div>
              <span className="mono">${stats.cost.toFixed(3)}</span>
            </div>
          ))}
        </div>
      )}

      <h2 style={{marginTop:36}}>Recent content</h2>
      {items.length === 0 ? (
        <p className="note">No content yet. Agents will fill this as they work.</p>
      ) : (
        <div className="steps" style={{marginTop:12}}>
          {items.slice(0,10).map((it:any)=>(
            <div key={it.id} className="step">
              <div style={{display:"flex",justifyContent:"space-between"}}>
                <h4 style={{margin:0}}>{it.topic}</h4>
                <span className="tag">{it.status}</span>
              </div>
              <p className="note" style={{margin:"4px 0 0"}}>{new Date(it.created_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
