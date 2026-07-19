"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

type Evt = { id?: number; agent: string; action: string; message: string; status: string; cost_usd?: number; created_at: string };

const DEMO_EVENTS: Evt[] = [
  { agent: "system", action: "waiting for worker", message: "Pipeline hasn't connected yet. Once your Railway worker boots and the first tick runs you'll see real chatter here.", status: "warn", created_at: new Date().toISOString() },
  { agent: "strategy", action: "stand by", message: "Waiting for the planner to wake up…", status: "info", created_at: new Date(Date.now()-60000).toISOString() },
];

const AGENT_META: Record<string,{label:string;color:string;emoji:string}> = {
  system:    { label: "System",    color: "#94a3b8", emoji: "🤖" },
  strategy:  { label: "Planner",   color: "#a78bfa", emoji: "🧠" },
  brain:     { label: "Writer",    color: "#60a5fa", emoji: "✍️" },
  qa:        { label: "QA",        color: "#f87171", emoji: "🔍" },
  visuals:   { label: "Visuals",   color: "#fbbf24", emoji: "🎨" },
  voice:     { label: "Voice",     color: "#34d399", emoji: "🎙️" },
  composer:  { label: "Editor",    color: "#22d3ee", emoji: "🎬" },
  publisher: { label: "Publisher", color: "#10b981", emoji: "📤" },
  analyst:   { label: "Analytics", color: "#f472b6", emoji: "📊" },
  community: { label: "Community", color: "#f59e0b", emoji: "💬" },
  digest:    { label: "Digest",    color: "#94a3b8", emoji: "📬" },
  budget:    { label: "Budget",    color: "#4ade80", emoji: "💰" },
  architect: { label: "Architect", color: "#f472b6", emoji: "🏗️" },
  strategist:{ label: "Strategist",color: "#eab308", emoji: "📋" },
  you:       { label: "You",       color: "#e2e8f0", emoji: "👤" },
};

function ago(iso: string) {
  const s = Math.floor((Date.now()-new Date(iso).getTime())/1000);
  if (s<0) return "just now";
  if (s<60) return s+"s ago";
  if (s<3600) return Math.floor(s/60)+"m ago";
  return Math.floor(s/3600)+"h ago";
}

function pipelineStatus(events: Evt[]): {label:string;color:string} {
  if (!events.length) return { label: "connecting…", color: "#f59e0b" };
  const latest = events.reduce((a,b)=> new Date(a.created_at)>new Date(b.created_at)?a:b, events[0]);
  const age = (Date.now()-new Date(latest.created_at).getTime())/1000;
  if (age < 180) return { label: "online  🟢", color: "#10b981" };
  if (age < 600) return { label: "idle  🟡",     color: "#f59e0b" };
  return { label: "offline  🔴", color: "#ef4444" };
}

export default function WorkspacePage() {
  const [events, setEvents] = useState<Evt[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [command, setCommand] = useState("");
  const [sending, setSending] = useState(false);
  const [polling, setPolling] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  async function load() {
    let gotReal = false;
    try {
      const r = await fetch("/api/workspace/events?limit=200", { cache: "no-store" });
      if (r.ok) {
        const j = await r.json();
        const list = Array.isArray(j?.events) ? j.events : [];
        if (list.length > 0) {
          setEvents(list);
          gotReal = true;
        }
      }
    } catch {}
    if (!gotReal && events.length === 0) {
      setEvents(DEMO_EVENTS);
    }
    setLoaded(true);
  }
  useEffect(() => {
    load();
    const id = polling ? setInterval(load, 5000) : undefined;
    return () => { if (id) clearInterval(id); };
  }, [polling]);

  async function sendOrder() {
    const text = command.trim();
    if (!text || sending) return;
    setSending(true);
    const ev: Evt = { agent: "you", action: "order", message: text, status: "info", created_at: new Date().toISOString() };
    setEvents(prev => [ev, ...prev]);
    setCommand("");
    // Optimistic acknowledgement from strategy
    setTimeout(() => {
      setEvents(prev => [{
        agent: "strategy", action: "order received",
        message: "Queued: '" + text.slice(0,120) + "' — will be picked up on the next tick.",
        status: "success", created_at: new Date().toISOString(),
      }, ...prev]);
    }, 600);
    try {
      await fetch("/api/studio", { method: "POST", headers: { "Content-Type":"application/json" },
        body: JSON.stringify({ action: "queue_topic", topic: text, source: "workspace-order" }) });
    } catch {}
    setSending(false);
  }

  const agents = Array.from(new Set(events.map(e=>e.agent)));
  const shown = filter === "all" ? events : events.filter(e=>e.agent===filter);
  const spend = events.reduce((a,e)=>a+Number(e.cost_usd||0),0);
  const errors = events.filter(e=>e.status==="error").length;
  const status = pipelineStatus(events);

  return (
    <div>
      <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:4}}>
        <h1 style={{margin:0}}>Agent workspace</h1>
        <span style={{fontSize:12,padding:"3px 10px",borderRadius:20,border:"1px solid "+status.color,color:status.color}}>
          Pipeline: {status.label}
        </span>
      </div>
      <p className="lead">Live feed of every agent working around the clock. Give them orders below — they queue topics, write scripts, generate visuals, edit video, and hand drafts back for your approval.</p>

      <div style={{display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginTop:20}}>
        <div className="card" style={{margin:0}}>
          <p className="note" style={{margin:0}}>Events</p>
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
        <div className="card" style={{margin:0}}>
          <p className="note" style={{margin:0}}>Last event</p>
          <h2 style={{margin:"4px 0",fontSize:18}}>{events.length ? ago(events.reduce((a,b)=>new Date(a.created_at)>new Date(b.created_at)?a:b,events[0]).created_at) : "—"}</h2>
        </div>
      </div>

      <div style={{display:"flex", gap:8, flexWrap:"wrap", marginTop:20, marginBottom:12}}>
        {["all", ...agents].map(a => {
          const meta = AGENT_META[a] || { label:a, color:"var(--dim)", emoji:"•" };
          const active = filter===a;
          return (
            <button key={a} onClick={()=>setFilter(a)}
              style={{
                padding:"6px 12px", borderRadius:20, cursor:"pointer", fontSize:12,
                border:"1px solid "+(active?meta.color:"var(--line)"),
                background: active?meta.color:"transparent",
                color: active?"#000":"inherit", fontWeight: active?600:400,
                display:"inline-flex",alignItems:"center",gap:6,
              }}>
              <span>{meta.emoji}</span>{meta.label}
            </button>
          );
        })}
        <label style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:6,fontSize:12,color:"var(--dim)"}}>
          <input type="checkbox" checked={polling} onChange={(e)=>setPolling(e.target.checked)} /> live (5s)
        </label>
      </div>

      <div ref={listRef} style={{border:"1px solid var(--line)",borderRadius:12,overflow:"hidden",background:"var(--bg)"}}>
        {!loaded ? (
          <div style={{padding:32,textAlign:"center"}} className="note">Loading agents…</div>
        ) : shown.length === 0 ? (
          <div style={{padding:32,textAlign:"center"}} className="note">No events for this filter.</div>
        ) : shown.map((e,i) => {
          const meta = AGENT_META[e.agent] || { label:e.agent, color:"var(--dim)", emoji:"•" };
          return (
            <div key={e.id ?? i} style={{
              display:"grid", gridTemplateColumns:"80px 130px 1fr 70px", gap:12, padding:"10px 14px",
              borderBottom:"1px solid var(--line)", alignItems:"baseline", fontSize:13,
              background: e.status==="error" ? "rgba(239,68,68,0.07)"
                        : e.status==="warn"  ? "rgba(245,158,11,0.06)"
                        : e.status==="success" ? "rgba(16,185,129,0.04)"
                        : e.status==="debate" ? "rgba(168,85,247,0.05)"
                        : "transparent",
            }}>
              <span className="mono" style={{fontSize:11,color:"var(--dim)"}}>{ago(e.created_at)}</span>
              <span style={{display:"flex",alignItems:"center",gap:6,fontWeight:600}}>
                <span>{meta.emoji}</span>{meta.label}
              </span>
              <span style={{minWidth:0}}>
                <b style={{marginRight:6,color:meta.color}}>{e.action}</b>
                <span className="note" style={{fontSize:13}}>{e.message}</span>
              </span>
              <span className="mono" style={{fontSize:11,color:"var(--dim)",textAlign:"right"}}>
                {e.cost_usd ? "$"+Number(e.cost_usd).toFixed(3) : ""}
              </span>
            </div>
          );
        })}
      </div>

      {/* Give orders */}
      <div className="card" style={{marginTop:20}}>
        <h3>Give agents an order</h3>
        <p className="note" style={{marginTop:-6}}>Type a topic or task and the strategist will queue it within one tick (~60s).</p>
        <div style={{display:"flex",gap:8,marginTop:10}}>
          <input value={command} onChange={(e)=>setCommand(e.target.value)}
            onKeyDown={(e)=>{ if(e.key==="Enter" && !sending) sendOrder(); }}
            placeholder='e.g. "Make a Reel about the new Claude Projects feature"'
            style={{flex:1,background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit"}}/>
          <button onClick={sendOrder} disabled={sending}>{sending?"Sending…":"Send →"}</button>
        </div>
        <div style={{display:"flex",gap:8,flexWrap:"wrap",marginTop:10}}>
          {["Make 3 Reels on the biggest AI news today",
            "Research 5 trending products for my store",
            "Rewrite the hook on the last draft — make it punchier",
            "Plan a week of YouTube Shorts around AI tools"].map(s => (
            <button key={s} onClick={()=>setCommand(s)} style={{fontSize:11,padding:"4px 10px",borderRadius:16,background:"transparent",border:"1px solid var(--line)",color:"var(--dim)",cursor:"pointer"}}>{s}</button>
          ))}
        </div>
      </div>

      <p className="note" style={{marginTop:20}}>
        Approve finished drafts from <Link href="/studio" style={{color:"var(--scheduled)"}}>Studio →</Link>.
        The Python worker writes these events directly into Supabase; this page polls every 5 seconds.
      </p>
    </div>
  );
}
