"use client";
import { useEffect, useState } from "react";

type Decision = { id: number; ts: string; department: string; action: string; estimated_cost_usd: number; decision: string; reason: string; account_id: string | null };
type Alloc = { account_id: string; budget_usd: number; max_posts: number; focus: string; note: string; model_tier: string };
type Roi = { account_id: string; day: string; spend_usd: number; revenue_usd: number; views: number; likes: number; comments: number; shares: number; followers_gained: number; roi_multiple: number | null };
type Rec = { id: number; ts: string; severity: string; category: string; recommendation: string; reasoning: string; projected_roi: number | null; projected_value_usd: number | null; account_id: string | null; applied: boolean };
type Data = { summary: any; decisions: Decision[]; allocations: Alloc[]; roi: Roi[]; recommendations: Rec[] };

const DEC_COLOR: Record<string,string> = {
  approve: "var(--published,#22c55e)",
  deny: "#ef4444", delay: "#f59e0b", reuse: "#3b82f6", cheaper: "#8b5cf6",
};
const SEV_COLOR: Record<string,string> = {
  critical: "#ef4444", action: "#f59e0b", opportunity: "var(--published,#22c55e)", info: "#3b82f6",
};
const FOCUS_EMOJI: Record<string,string> = {
  grow:"🚀", pause:"⏸", profit:"💰", balanced:"⚖️", evergreen:"♻️", maintain:"🔒", engage:"💬",
};

export default function CEOv2Page() {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [tab, setTab] = useState<"overview"|"decisions"|"alloc"|"roi"|"recs">("overview");

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/ceo-decisions?days=3", { cache: "no-store" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error);
      setData(j);
    } catch (e:any) { setErr(e.message); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); const i = setInterval(load, 15000); return () => clearInterval(i); }, []);

  const act = async (id: number, action: "apply"|"dismiss") => {
    await fetch("/api/ceo-decisions", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ id, action })});
    load();
  };

  if (loading && !data) return <div><h1>CEO Console (v5.5)</h1><p className="note">Loading…</p></div>;
  if (err) return <div><h1>CEO Console</h1><p className="note" style={{color:"#ef4444"}}>{err}</p></div>;
  if (!data) return null;
  const s = data.summary;
  const today = new Date().toISOString().slice(0,10);

  return (
    <div>
      <h1>👔 CEO Console <span className="tag" style={{marginLeft:8, fontSize:11}}>v5.5</span></h1>
      <p className="note" style={{maxWidth:760}}>
        Every AI spend decision is routed through the CEO engine before money is spent.
        Decisions are approved/denied/delayed/reused based on expected ROI, account history,
        budget, and asset reuse. Below is the real-time audit trail.
      </p>

      {/* Tabs */}
      <div style={{display:"flex", gap:6, marginTop:16, marginBottom:16, flexWrap:"wrap"}}>
        {([["overview","Overview"],["decisions",`Decisions (${s.total_decisions})`],["alloc","Today's Budget"],["roi","ROI"],["recs",`Recommendations (${data.recommendations.length})`]] as const).map(([k,l]) => (
          <button key={k} onClick={()=>setTab(k)} className={tab===k?"primary":""}
            style={{padding:"8px 14px",border:"1px solid var(--line)",borderRadius:8,cursor:"pointer",
              background:tab===k?"var(--approved)":"var(--card)",color:tab===k?"#fff":"inherit",fontSize:13}}>{l}</button>
        ))}
        <button onClick={load} style={{marginLeft:"auto",padding:"8px 14px",border:"1px solid var(--line)",borderRadius:8,cursor:"pointer",fontSize:13}}>↻ Refresh</button>
      </div>

      {tab==="overview" && (<>
        <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(180px,1fr))",gap:12}}>
          <Stat label="Approved" value={s.approved} color="var(--published,#22c55e)" />
          <Stat label="Denied $-wasters" value={s.denied} color="#ef4444" />
          <Stat label="Delayed" value={s.delayed} color="#f59e0b" />
          <Stat label="♻️ Reused (free)" value={s.reused} color="#3b82f6" />
          <Stat label="⬇ Cheaper alt used" value={s.cheaper} color="#8b5cf6" />
          <Stat label="$ Saved by reuse" value={`$${s.total_reuse_savings.toFixed(3)}`} color="#3b82f6" />
          <Stat label="$ Considered" value={`$${s.total_est_cost.toFixed(3)}`} />
        </div>

        <h2 style={{marginTop:28}}>⚡ Today's recommendations</h2>
        <div style={{display:"grid",gap:8}}>
          {data.recommendations.slice(0,5).map(r => (
            <RecCard key={r.id} r={r} onAct={act} compact />
          ))}
          {data.recommendations.length===0 && <p className="note">No recommendations right now — data building.</p>}
        </div>

        <h2 style={{marginTop:28}}>📊 Today's allocation</h2>
        <div style={{display:"grid",gap:8}}>
          {data.allocations.map(a => (
            <div key={a.account_id} className="card" style={{padding:12,borderLeft:`4px solid ${a.focus==="pause"?"#ef4444":a.focus==="grow"?"var(--published)":"var(--line)"}`}}>
              <div style={{display:"flex",gap:12,alignItems:"baseline",flexWrap:"wrap"}}>
                <b>{FOCUS_EMOJI[a.focus]||"•"} {a.focus}</b>
                <span className="mono" style={{fontSize:12,opacity:0.7}}>acc:{a.account_id.slice(0,8)}…</span>
                <span style={{marginLeft:"auto"}}>${Number(a.budget_usd).toFixed(2)} · {a.max_posts} posts · {a.model_tier}</span>
              </div>
              <div className="note" style={{fontSize:12,marginTop:4}}>{a.note}</div>
            </div>
          ))}
          {data.allocations.length===0 && <p className="note">No allocations yet — wait for CEO daily tick.</p>}
        </div>
      </>)}

      {tab==="decisions" && (
        <div style={{display:"grid",gap:6}}>
          {data.decisions.slice(0,80).map(d => (
            <div key={d.id} className="card" style={{padding:10,borderLeft:`3px solid ${DEC_COLOR[d.decision]||"#888"}`}}>
              <div style={{display:"flex",gap:10,alignItems:"baseline",fontSize:12,flexWrap:"wrap"}}>
                <span className="mono" style={{color:DEC_COLOR[d.decision]||"#888",fontWeight:700,minWidth:60}}>{d.decision.toUpperCase()}</span>
                <b>{d.department}.{d.action}</b>
                <span className="mono" style={{opacity:0.6}}>${Number(d.estimated_cost_usd).toFixed(3)}</span>
                <span className="note" style={{marginLeft:"auto",fontSize:11}}>{new Date(d.ts).toLocaleTimeString()}</span>
              </div>
              <div className="note" style={{fontSize:12,marginTop:3}}>{d.reason}</div>
            </div>
          ))}
        </div>
      )}

      {tab==="alloc" && (
        <div style={{display:"grid",gap:10}}>
          {data.allocations.map(a => (
            <div key={a.account_id} className="card" style={{padding:14,borderLeft:`4px solid ${a.focus==="pause"?"#ef4444":a.focus==="grow"?"var(--published)":"var(--line)"}`}}>
              <div style={{display:"flex",gap:12,alignItems:"center",flexWrap:"wrap"}}>
                <b style={{fontSize:18}}>{FOCUS_EMOJI[a.focus]||"•"} {a.focus.toUpperCase()}</b>
                <span className="mono" style={{fontSize:11,opacity:0.6}}>{a.account_id}</span>
                <span style={{marginLeft:"auto",fontSize:22,fontWeight:700}}>${Number(a.budget_usd).toFixed(2)}</span>
              </div>
              <div style={{display:"flex",gap:14,marginTop:8,flexWrap:"wrap"}}>
                <span className="tag">max posts: {a.max_posts}</span>
                <span className="tag">model tier: {a.model_tier}</span>
              </div>
              <div className="note" style={{marginTop:8}}>{a.note}</div>
            </div>
          ))}
        </div>
      )}

      {tab==="roi" && (
        <div style={{display:"grid",gap:8}}>
          <div className="card" style={{padding:10,display:"grid",gridTemplateColumns:"repeat(7,1fr)",fontSize:11,gap:8,fontWeight:600}}>
            <span>Account</span><span>Spend</span><span>Rev</span><span>ROI</span><span>Views</span><span>Followers</span><span>Eng.</span>
          </div>
          {data.roi.map(r => {
            const eng = (r.likes||0)+(r.comments||0)+(r.shares||0);
            const roi = r.roi_multiple;
            return (
              <div key={r.account_id+r.day} className="card" style={{padding:10,display:"grid",gridTemplateColumns:"repeat(7,1fr)",fontSize:12,gap:8,borderLeft:`3px solid ${roi&&roi>=1?"var(--published)":roi&&roi<0.5?"#ef4444":"var(--line)"}`}}>
                <span className="mono">{r.account_id.slice(0,8)}…</span>
                <span>${Number(r.spend_usd).toFixed(3)}</span>
                <span>${Number(r.revenue_usd).toFixed(2)}</span>
                <span style={{color:roi&&roi>=1?"var(--published)":roi&&roi<0.5?"#ef4444":"#aaa",fontWeight:700}}>{roi?`${roi.toFixed(2)}x`:"—"}</span>
                <span>{(r.views||0).toLocaleString()}</span>
                <span>{(r.followers_gained||0).toLocaleString()}</span>
                <span>{eng.toLocaleString()}</span>
              </div>
            );
          })}
          {data.roi.length===0 && <p className="note">No ROI snapshots yet — they populate after a day of production.</p>}
        </div>
      )}

      {tab==="recs" && (
        <div style={{display:"grid",gap:10}}>
          {data.recommendations.map(r => <RecCard key={r.id} r={r} onAct={act} />)}
          {data.recommendations.length===0 && <p className="note">No open recommendations.</p>}
        </div>
      )}
    </div>
  );
}

function Stat({label,value,color}:{label:string;value:any;color?:string}){
  return <div className="card" style={{padding:14}}>
    <div style={{fontSize:11,opacity:0.7,textTransform:"uppercase",letterSpacing:0.5}}>{label}</div>
    <div style={{fontSize:22,fontWeight:700,color:color||"inherit",marginTop:4}}>{value}</div>
  </div>;
}

function RecCard({r,onAct,compact=false}:{r:Rec;onAct:(id:number,a:"apply"|"dismiss")=>void;compact?:boolean}){
  return <div key={r.id} className="card" style={{padding:compact?10:14,borderLeft:`4px solid ${SEV_COLOR[r.severity]||"#888"}`}}>
    <div style={{display:"flex",gap:10,alignItems:"baseline",flexWrap:"wrap"}}>
      <span className="tag" style={{background:SEV_COLOR[r.severity]||"#888",color:"#fff",fontSize:10}}>{r.severity.toUpperCase()}</span>
      <span className="tag" style={{fontSize:10}}>{r.category}</span>
      {r.projected_roi && <span className="mono" style={{fontSize:11,color:"var(--published)"}}>{r.projected_roi}x ROI</span>}
      {r.projected_value_usd ? <span className="mono" style={{fontSize:11,opacity:0.7}}>~${r.projected_value_usd.toFixed(2)} value</span> : null}
      {!compact && <div style={{marginLeft:"auto",display:"flex",gap:6}}>
        {!r.applied && <button onClick={()=>onAct(r.id,"apply")} style={{padding:"4px 10px",fontSize:12}}>Apply</button>}
        <button onClick={()=>onAct(r.id,"dismiss")} style={{padding:"4px 10px",fontSize:12,opacity:0.6}}>Dismiss</button>
      </div>}
    </div>
    <div style={{fontWeight:600,marginTop:6}}>{r.recommendation}</div>
    <div className="note" style={{fontSize:12,marginTop:4}}>{r.reasoning}</div>
  </div>;
}
