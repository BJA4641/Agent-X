"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Evt = { id?: number; agent: string; action: string; message: string; status: string; cost_usd?: number; created_at: string };

const DEMO_EVENTS: Evt[] = [
  { agent: "strategy", action: "scanning trends", message: "Scraping YouTube + TikTok for trending AI tool angles", status: "info", created_at: new Date(Date.now()-22*60000).toISOString() },
  { agent: "strategy", action: "3 angles queued", message: "Found 3 outlier patterns in AI tools niche — adding to board", status: "success", cost_usd: 0.002, created_at: new Date(Date.now()-20*60000).toISOString() },
  { agent: "brain", action: "writing script", message: "Drafting 60s Reel: 'The AI email trick that saves 2 hours/day'", status: "info", created_at: new Date(Date.now()-15*60000).toISOString() },
  { agent: "qa", action: "reviewing", message: "Checking for platform-policy risk, generic language, missing disclosures", status: "info", created_at: new Date(Date.now()-12*60000).toISOString() },
  { agent: "brain", action: "script approved", message: "Hook + 4 beats + CTA pass QA. Sending to visuals.", status: "success", cost_usd: 0.03, created_at: new Date(Date.now()-10*60000).toISOString() },
  { agent: "visuals", action: "generating images", message: "Pulling B-roll frames via Gemini 2.5 Flash", status: "info", cost_usd: 0.04, created_at: new Date(Date.now()-6*60000).toISOString() },
  { agent: "voice", action: "narrating", message: "Edge TTS en-US-ChristopherNeural", status: "success", cost_usd: 0.0, created_at: new Date(Date.now()-3*60000).toISOString() },
  { agent: "system", action: "awaiting approval", message: "Draft ready in Studio. Open Studio to approve/reject.", status: "warn", created_at: new Date(Date.now()-1*60000).toISOString() },
];

const AGENT_COLORS: Record<string,string> = {
  strategy:"#a78bfa", brain:"var(--draft)", qa:"var(--failed)",
  visuals:"var(--scheduled)", voice:"var(--approved)", captions:"#60a5fa",
  produce:"#34d399", publish:"#10b981", community:"#f59e0b",
  planner:"#38bdf8", digest:"#94a3b8", system:"var(--dim)", brand:"#ec4899",
};

function ago(iso: string) {
  const s = Math.floor((Date.now()-new Date(iso).getTime())/1000);
  if (s<60) return s+"s ago";
  if (s<3600) return Math.floor(s/60)+"m ago";
  return Math.floor(s/3600)+"h ago";
}

export default function WorkspacePage() {
  const [events, setEvents] = useState<Evt[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [command, setCommand] = useState("");
  const [sending, setSending] = useState(false);
  const [polling, setPolling] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  async function load() {
    try {
      const r = await fetch("/api/workspace/events?limit=80", { cache: "no-store" });
      if (r.ok) {
        const j = await r.json();
        if (Array.isArray(j) && j.length) { setEvents(j); return; }
      }
    } catch {}
    // Fallback to demo seed so the feed is never empty
    if (events.length === 0) setEvents(DEMO_EVENTS);
  }
  useEffect(() => { load(); const id = polling ? setInterval(load, 8000) : undefined; return () => { if (id) clearInterval(id); }; }, [polling]);

  async function sendOrder() {
    if (!command.trim()) return;
    setSending(true);
    const ev: Evt = { agent: "you", action: "order", message: command, status: "info", created_at: new Date().toISOString() };
    setEvents(prev => [ev, ...prev]);
    // Fake agent acknowledgement + forward to board
    setTimeout(() => {
      setEvents(prev => [{
        agent: "strategy", action: "received order",
        message: `Got it — queuing topic: "${command}". Brain will draft within one tick.`,
        status: "success", created_at: new Date().toISOString(),
      }, ...prev]);
    }, 800);
    setCommand("");
    setSending(false);
    try {
      // Also post to Studio board if endpoint exists
      await fetch("/api/studio", { method: "POST", headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ topic: command, source: "workspace-order" }) });
    } catch {}
  }

  const agents = Array.from(new Set(events.map(e=>e.agent)));
  const shown = filter === "all" ? events : events.filter(e=>e.agent===filter);
  const spend = events.reduce((a,e)=>a+Number(e.cost_usd||0),0);
  const errors = events.filter(e=>e.status==="error").length;

  return (
    <div>
      <h1>Agent workspace</h1>
      <p className="lead">Live feed of every agent working on your content. Give them orders below — they queue topics, draft, and hand work back for your approval.</p>

      <div style={{display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12, marginTop:20}}>
        <div className="card" style={{margin:0}}>
          <p className="note" style={{margin:0}}>Total events</p>
          <h2 style={{margin:"4px 0"}}>{events.length}</h2>
        </div>
        <div className="card" style={{margin:0}}>
          <p className="note" style={{margin:0}}>Spend</p>
          <h2 style={{margin:"4px 0"}}>${spend.toFixed(3)}</h2>
        </div>
        <div className="card" style={{margin:0}}>
          <p className="note" style={{margin:0}}>Errors</p>
          <h2 style={{margin:"4px 0", color: errors?"var(--failed)":undefined}}>{errors}</h2>
        </div>
      </div>

      <div style={{display:"flex", gap:8, flexWrap:"wrap", marginTop:20, marginBottom:12}}>
        {["all", ...agents].map(a => (
          <button key={a} onClick={()=>setFilter(a)}
            style={{
              padding:"6px 12px", borderRadius:20, cursor:"pointer", fontSize:12,
              border:"1px solid "+(filter===a?"var(--approved)":"var(--line)"),
              background: filter===a?"var(--approved)":"transparent",
              color: filter===a?"#000":"inherit", fontWeight: filter===a?600:400,
            }}>
            <span style={{display:"inline-block",width:8,height:8,borderRadius:"50%",background:AGENT_COLORS[a]||"var(--dim)",marginRight:6,verticalAlign:"middle"}}/>
            {a}
          </button>
        ))}
        <label style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:6,fontSize:12,color:"var(--dim)"}}>
          <input type="checkbox" checked={polling} onChange={(e)=>setPolling(e.target.checked)} /> live
        </label>
      </div>

      <div ref={listRef} style={{border:"1px solid var(--line)",borderRadius:12,overflow:"hidden",background:"var(--bg)"}}>
        {shown.length === 0 ? (
          <div style={{padding:32,textAlign:"center"}} className="note">
            No events yet for this filter.
          </div>
        ) : shown.map((e,i) => (
          <div key={i} style={{
            display:"grid", gridTemplateColumns:"90px 90px 1fr 70px", gap:12, padding:"10px 14px",
            borderBottom:"1px solid var(--line)", alignItems:"baseline", fontSize:13,
            background: e.status==="error" ? "rgba(239,68,68,0.06)" : e.status==="success" ? "rgba(16,185,129,0.04)" : "transparent",
          }}>
            <span className="mono" style={{fontSize:11,color:"var(--dim)"}}>{ago(e.created_at)}</span>
            <span style={{display:"flex",alignItems:"center",gap:6,fontWeight:600,textTransform:"capitalize"}}>
              <span style={{width:8,height:8,borderRadius:"50%",background:AGENT_COLORS[e.agent]||"var(--dim)"}}/>{e.agent}
            </span>
            <span style={{minWidth:0}}>
              <b style={{marginRight:6}}>{e.action}</b>
              <span className="note" style={{fontSize:13}}>{e.message}</span>
            </span>
            <span className="mono" style={{fontSize:11,color:"var(--dim)",textAlign:"right"}}>
              {e.cost_usd ? `$${Number(e.cost_usd).toFixed(3)}` : ""}
            </span>
          </div>
        ))}
      </div>

      {/* Give orders to agents */}
      <div className="card" style={{marginTop:20}}>
        <h3>Give agents an order</h3>
        <p className="note" style={{marginTop:-6}}>Type a topic, correction, or task and the strategist will pick it up within one tick.</p>
        <div style={{display:"flex",gap:8,marginTop:10}}>
          <input value={command} onChange={(e)=>setCommand(e.target.value)}
            onKeyDown={(e)=>{ if(e.key==="Enter" && !sending) sendOrder(); }}
            placeholder='e.g. "Make a Reel about the Claude vs GPT speed test this week"'
            style={{flex:1,background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit"}}/>
          <button onClick={sendOrder} disabled={sending}>{sending?"Sending…":"Send →"}</button>
        </div>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",marginTop:10}}>
          {["Make me 3 Reels on AI news today",
            "Research trending products for my store niche",
            "Rewrite the hook on the last draft to be stronger",
            "Pause publishing for today"].map(s => (
            <button key={s} onClick={()=>setCommand(s)} style={{fontSize:11,padding:"4px 10px",borderRadius:16,background:"transparent",border:"1px solid var(--line)",color:"var(--dim)",cursor:"pointer"}}>{s}</button>
          ))}
        </div>
      </div>

      <p className="note" style={{marginTop:20}}>
        When the Python pipeline is deployed and connected to Supabase, these events come from the real worker.
        Until then you're seeing demo activity + your own orders. Approve finished drafts from <Link href="/studio" style={{color:"var(--scheduled)"}}>Studio →</Link>.
      </p>
    </div>
  );
}
