"use client";
import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";

type Project = { id: string; name: string; niche: string; paused: boolean; daily_budget_usd: number; cta?: string; status: string };
type Account = {
  id: string; name: string; handle: string; status: string; avatar_emoji: string; paused: boolean; niche: string;
  daily_budget_usd: number;
  counts: { planned: number; drafted: number; published: number; rejected: number; avg_grade: number; passed: number };
};
type MemEntry = { id: string; role: string; content: string; created_at: string; account_id?: string | null };
type Event = { id: string; agent: string; message: string; level: string; event_type: string; created_at: string; emoji?: string; color?: string };

const AGENT_META: Record<string,{ emoji: string; label: string; color: string }> = {
  architect:  { emoji:"🏛️", label:"Architect",    color:"#a78bfa" },
  strategist: { emoji:"📊", label:"Strategist",   color:"#f59e0b" },
  brain:      { emoji:"🧠", label:"Writer",       color:"#22d3ee" },
  grader:     { emoji:"🎯", label:"Grader",       color:"#ef4444" },
  visuals:    { emoji:"🎨", label:"Visuals",      color:"#ec4899" },
  voice:      { emoji:"🎙️", label:"Voice",        color:"#06b6d4" },
  composer:   { emoji:"🎬", label:"Composer",     color:"#10b981" },
  publisher:  { emoji:"📤", label:"Publisher",    color:"#3b82f6" },
  qa:         { emoji:"🔍", label:"QA",           color:"#06b6d4" },
  analyst:    { emoji:"📈", label:"Analyst",      color:"#8b5cf6" },
  scout:      { emoji:"🔭", label:"Trend Scout",  color:"#f97316" },
  community:  { emoji:"💬", label:"Community",    color:"#14b8a6" },
  digest:     { emoji:"📋", label:"Digest",       color:"#64748b" },
  budget:     { emoji:"💰", label:"Budget",       color:"#eab308" },
  system:     { emoji:"⚙️", label:"System",       color:"#64748b" },
};

function gradeColor(n:number){ if(n>=9) return "#10b981"; if(n>=8) return "#22c55e"; if(n>=7) return "#eab308"; if(n>=5) return "#f97316"; return "#ef4444"; }

export default function ProjectConsolePage() {
  const { pid } = useParams<{pid:string}>();
  const [project, setProject] = useState<Project|null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [projectMem, setProjectMem] = useState<MemEntry[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [tab, setTab] = useState<"live"|"chat"|"manual"|"perf">("live");
  const [chatText, setChatText] = useState("");
  const [sendingChat, setSendingChat] = useState(false);
  const [manualTopic, setManualTopic] = useState("");
  const [manualAcc, setManualAcc] = useState<string>("");
  const [manualCount, setManualCount] = useState(1);
  const [queued, setQueued] = useState<number|null>(null);
  const [loading, setLoading] = useState(true);
  const chatRef = useRef<HTMLDivElement>(null);
  const eventsRef = useRef<HTMLDivElement>(null);

  async function refresh() {
    const r = await fetch(`/api/projects/${pid}/console`, { cache: "no-store" });
    if (r.ok) {
      const j = await r.json();
      setProject(j.project);
      setAccounts(j.accounts);
      setProjectMem(j.project_memory||[]);
      setEvents(j.events||[]);
    }
    setLoading(false);
  }

  useEffect(()=>{ if(pid) refresh(); }, [pid]);
  useEffect(()=>{
    if(!pid) return;
    const id = setInterval(refresh, 5000);
    return ()=>clearInterval(id);
  },[pid]);
  useEffect(()=>{
    if(eventsRef.current) eventsRef.current.scrollTop = eventsRef.current.scrollHeight;
  },[events, tab]);
  useEffect(()=>{
    if(chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  },[projectMem, tab]);

  async function toggleProjectPaused() {
    if(!project) return;
    await fetch(`/api/projects`,{
      method:"PATCH", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({id:pid, paused:!project.paused})
    });
    refresh();
  }
  async function toggleAccount(aid:string, paused:boolean) {
    await fetch(`/api/projects/${pid}/accounts/${aid}`,{
      method:"PATCH", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({paused})
    });
    refresh();
  }
  async function sendChat() {
    const t = chatText.trim();
    if(!t||sendingChat) return;
    setSendingChat(true);
    await fetch(`/api/projects/${pid}/chat`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body: JSON.stringify({content:t})
    });
    setChatText(""); setSendingChat(false); refresh();
  }
  async function queueManual() {
    setQueued(null);
    const r = await fetch(`/api/projects/${pid}/generate`,{
      method:"POST",headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        account_id: manualAcc||undefined,
        topic: manualTopic||undefined,
        count: manualCount,
      })
    });
    const j = await r.json();
    if(r.ok){ setQueued(j.queued); setManualTopic(""); setTimeout(()=>setQueued(null),3000); }
    else alert("Error: "+(j.error||"unknown"));
  }

  if(loading) return <p className="note">Loading console…</p>;
  if(!project) return <p className="note">Project not found.</p>;

  const activeAcc = accounts.filter(a=>!a.paused).length;
  const totalPlanned = accounts.reduce((s,a)=>s+a.counts.planned,0);
  const totalDrafted = accounts.reduce((s,a)=>s+a.counts.drafted,0);
  const totalPassed  = accounts.reduce((s,a)=>s+a.counts.passed,0);
  const avgGrade = accounts.filter(a=>a.counts.avg_grade>0).reduce((s,a)=>s+a.counts.avg_grade,0) / Math.max(1,accounts.filter(a=>a.counts.avg_grade>0).length);

  return (
    <div>
      <div style={{marginBottom:8}}>
        <Link href={`/dashboard/projects/${pid}`} className="note" style={{fontSize:13}}>← Back to accounts</Link>
      </div>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"}}>
        <div>
          <h1 style={{margin:0}}>🎛️ AI Console — {project.name}</h1>
          <p className="note" style={{margin:"4px 0 0"}}>
            {project.niche.replace(/_/g," ")} · ${project.daily_budget_usd.toFixed(2)}/day ·
            {" "}{activeAcc}/{accounts.length} accounts active
          </p>
        </div>
        <button onClick={toggleProjectPaused}
                style={{background: project.paused?"#10b981":"#ef4444", border:"none"}}>
          {project.paused?"▶ Resume project":"⏸ Pause project"}
        </button>
      </div>

      {project.paused && (
        <div className="card" style={{margin:"12px 0",borderColor:"#ef4444",background:"rgba(239,68,68,0.08)"}}>
          <b>⏸ Project PAUSED</b> — no agents are working. Hit Resume to start.
        </div>
      )}

      {/* KPI row */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(150px,1fr))",gap:10,margin:"18px 0"}}>
        <KPI label="Active accounts" value={`${activeAcc}`} icon="🤖" />
        <KPI label="Posts planned" value={`${totalPlanned}`} icon="📋" />
        <KPI label="Drafts ready" value={`${totalDrafted}`} icon="✨" />
        <KPI label="Passed 8/10" value={`${totalPassed}`} icon="✅" />
        <KPI label="Avg grade" value={avgGrade?avgGrade.toFixed(1)+"/10":"—"} icon="🎯" color={avgGrade?gradeColor(avgGrade):undefined} />
      </div>

      {/* Tabs */}
      <div style={{display:"flex",gap:6,flexWrap:"wrap",margin:"10px 0 16px",borderBottom:"1px solid var(--line)",paddingBottom:8}}>
        {([
          ["live","🔴 Live agents"],
          ["chat","💬 Chat with all agents"],
          ["manual","⚡ Generate manually"],
          ["perf","📊 Performance"],
        ] as const).map(([k,l])=>(
          <button key={k} onClick={()=>setTab(k)}
            style={{padding:"8px 14px",borderRadius:10,cursor:"pointer",fontSize:13,
                    border:"1px solid "+(tab===k?"var(--scheduled)":"var(--line)"),
                    background:tab===k?"var(--scheduled)":"transparent",
                    color:tab===k?"#000":"inherit",fontWeight:tab===k?600:400}}>
            {l}
          </button>
        ))}
      </div>

      {/* LIVE */}
      {tab==="live" && (
        <div style={{display:"grid",gridTemplateColumns:"2fr 1fr",gap:16,alignItems:"start"}}>
          <div className="card" style={{padding:0,overflow:"hidden"}}>
            <div style={{padding:"10px 14px",borderBottom:"1px solid var(--line)",fontWeight:600,fontSize:13,display:"flex",justifyContent:"space-between"}}>
              <span>🔴 Live agent feed</span>
              <span className="note" style={{fontSize:11,fontWeight:400}}>updates every 5s</span>
            </div>
            <div ref={eventsRef} style={{height:500,overflowY:"auto",padding:10,background:"var(--bg)",fontFamily:"ui-monospace, monospace",fontSize:12}}>
              {events.length===0?<p className="note" style={{textAlign:"center",padding:40}}>Waiting for agents to start…</p>:events.map(e=>{
                const meta = AGENT_META[e.agent] || {emoji:"🤖",label:e.agent,color:"var(--dim)"};
                const time = new Date(e.created_at).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"});
                return (
                  <div key={e.id} style={{padding:"6px 8px",display:"flex",gap:8,alignItems:"flex-start",borderLeft:"3px solid "+meta.color,marginBottom:4,background:"rgba(255,255,255,0.02)"}}>
                    <span style={{fontSize:16,flexShrink:0}}>{meta.emoji}</span>
                    <div style={{flex:1}}>
                      <div style={{opacity:.5,fontSize:10}}>{time} · {meta.label}</div>
                      <div style={{color:e.level==="error"?"#ef4444":e.level==="warn"?"#f59e0b":"inherit"}}>{e.message}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div>
            <div className="card" style={{margin:0}}>
              <h3 style={{margin:"0 0 10px"}}>Accounts</h3>
              <div style={{display:"grid",gap:8}}>
                {accounts.map(a=>{
                  const g = a.counts.avg_grade;
                  return (
                    <div key={a.id} style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8,padding:8,border:"1px solid var(--line)",borderRadius:8,opacity:a.paused?0.5:1}}>
                      <div style={{display:"flex",alignItems:"center",gap:8,minWidth:0,flex:1}}>
                        <span style={{fontSize:20}}>{a.avatar_emoji}</span>
                        <div style={{minWidth:0}}>
                          <div style={{fontSize:12,fontWeight:600,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{a.name}</div>
                          <div className="note" style={{fontSize:10}}>@{a.handle} · {a.counts.passed}✅ {a.counts.drafted}📝</div>
                        </div>
                      </div>
                      {g>0 && <span style={{fontSize:11,padding:"2px 8px",borderRadius:20,background:gradeColor(g)+"22",color:gradeColor(g),fontWeight:700}}>{g.toFixed(1)}</span>}
                      <button onClick={()=>toggleAccount(a.id,!a.paused)}
                              style={{fontSize:10,padding:"4px 8px",borderRadius:6,cursor:"pointer",
                                      background:a.paused?"#10b98122":"#ef444422",color:a.paused?"#10b981":"#ef4444",
                                      border:"1px solid "+(a.paused?"#10b981":"#ef4444")}}>
                        {a.paused?"▶":"⏸"}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CHAT */}
      {tab==="chat" && (
        <div className="card" style={{maxWidth:800,padding:0,overflow:"hidden"}}>
          <div style={{padding:"10px 14px",borderBottom:"1px solid var(--line)",fontWeight:600,fontSize:13}}>
            💬 Project-wide chat — messages here apply to EVERY account in this project
          </div>
          <div ref={chatRef} style={{height:400,overflowY:"auto",padding:14,background:"var(--bg)"}}>
            {projectMem.length===0?<p className="note" style={{textAlign:"center",padding:40}}>
              Give your agents orders. They will see these before writing brand docs, planning posts, and writing scripts across ALL accounts in this project.
              <br/><br/>Examples:<br/>
              • "use deadpan humor, no hypey language"<br/>
              • "only promote tools I've personally tested"<br/>
              • "avoid AI-generated people images, use screen recordings"
            </p>:projectMem.map(m=>(
              <div key={m.id} style={{marginBottom:10,display:"flex",gap:8,justifyContent:"flex-end"}}>
                <div style={{maxWidth:"80%",padding:"10px 14px",borderRadius:12,
                             background:m.role==="user"?"var(--scheduled)22":"var(--card)",
                             border:"1px solid "+(m.role==="user"?"var(--scheduled)":"var(--line)"),
                             fontSize:13}}>
                  <div style={{fontSize:10,opacity:.6,marginBottom:3}}>
                    {m.role.toUpperCase()} · {new Date(m.created_at).toLocaleString()}
                  </div>
                  {m.content}
                </div>
                <span style={{fontSize:20}}>{m.role==="user"?"🧑‍💻":"🤖"}</span>
              </div>
            ))}
          </div>
          <div style={{display:"flex",gap:8,padding:10,borderTop:"1px solid var(--line)"}}>
            <input value={chatText} onChange={e=>setChatText(e.target.value)}
                   onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();sendChat();}}}
                   placeholder='e.g. "use faster cuts, make hooks 2 words max"'
                   style={{flex:1,background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit",fontSize:13}}/>
            <button onClick={sendChat} disabled={sendingChat||!chatText.trim()}>{sendingChat?"…":"Send →"}</button>
          </div>
        </div>
      )}

      {/* MANUAL GENERATE */}
      {tab==="manual" && (
        <div className="card" style={{maxWidth:600}}>
          <h3>⚡ Manually generate content</h3>
          <p className="note" style={{margin:"4px 0 16px"}}>
            Skip the queue and tell the AI to produce content for a specific account/topic RIGHT NOW.
            Pipeline picks it up on next tick (~60s). Content still goes through the grader (must pass 8/10).
          </p>
          <div style={{display:"grid",gap:12}}>
            <div>
              <label style={{fontSize:12,display:"block",marginBottom:4}}>Account (optional — picks first active account if blank)</label>
              <select value={manualAcc} onChange={e=>setManualAcc(e.target.value)}
                      style={{width:"100%",background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit"}}>
                <option value="">— auto-pick active account —</option>
                {accounts.filter(a=>!a.paused).map(a=>(
                  <option key={a.id} value={a.id}>{a.avatar_emoji} {a.name} (@{a.handle})</option>
                ))}
              </select>
            </div>
            <div>
              <label style={{fontSize:12,display:"block",marginBottom:4}}>Topic / specific instruction (optional)</label>
              <textarea value={manualTopic} onChange={e=>setManualTopic(e.target.value)}
                        placeholder='e.g. "how to use ChatGPT o3-mini to write cold emails"'
                        rows={3}
                        style={{width:"100%",background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit",resize:"vertical",fontSize:13,fontFamily:"inherit"}}/>
            </div>
            <div>
              <label style={{fontSize:12,display:"block",marginBottom:4}}>How many posts: {manualCount}</label>
              <input type="range" min={1} max={5} value={manualCount} onChange={e=>setManualCount(parseInt(e.target.value))} style={{width:"100%"}}/>
            </div>
            <button onClick={queueManual} disabled={project.paused} style={{background:"var(--scheduled)",border:"none"}}>
              🚀 Queue {manualCount} post{manualCount>1?"s":""}
            </button>
            {queued!==null && (
              <div style={{padding:10,borderRadius:8,background:"#10b98122",color:"#10b981",textAlign:"center",fontSize:13}}>
                ✅ Queued {queued} item(s) — agents pick it up within ~60 seconds
              </div>
            )}
            {project.paused && <p className="note" style={{color:"#ef4444"}}>Resume the project first to generate content.</p>}
          </div>
        </div>
      )}

      {/* PERFORMANCE */}
      {tab==="perf" && (
        <div>
          <div className="card" style={{maxWidth:800}}>
            <h3>Account performance</h3>
            <div style={{overflowX:"auto"}}>
              <table style={{width:"100%",borderCollapse:"collapse",fontSize:13,marginTop:10}}>
                <thead>
                  <tr style={{borderBottom:"1px solid var(--line)",textAlign:"left"}}>
                    <th style={{padding:"8px 10px"}}>Account</th>
                    <th style={{padding:"8px 10px"}}>Status</th>
                    <th style={{padding:"8px 10px",textAlign:"center"}}>Planned</th>
                    <th style={{padding:"8px 10px",textAlign:"center"}}>Drafts</th>
                    <th style={{padding:"8px 10px",textAlign:"center"}}>Passed</th>
                    <th style={{padding:"8px 10px",textAlign:"center"}}>Avg grade</th>
                    <th style={{padding:"8px 10px"}}></th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map(a=>(
                    <tr key={a.id} style={{borderBottom:"1px solid var(--line)",opacity:a.paused?.4:1}}>
                      <td style={{padding:"8px 10px"}}>
                        <Link href={`/dashboard/projects/${pid}/accounts/${a.id}`} style={{color:"var(--scheduled)",textDecoration:"none",display:"flex",alignItems:"center",gap:8}}>
                          <span style={{fontSize:18}}>{a.avatar_emoji}</span>
                          <div>
                            <div style={{fontWeight:600}}>{a.name}</div>
                            <div className="note" style={{fontSize:10}}>@{a.handle}</div>
                          </div>
                        </Link>
                      </td>
                      <td style={{padding:"8px 10px"}}>
                        <span style={{fontSize:11,padding:"2px 8px",borderRadius:20,
                                       background:a.paused?"#ef444433":"#10b98122",
                                       color:a.paused?"#ef4444":"#10b981"}}>
                          {a.paused?"paused":a.status}
                        </span>
                      </td>
                      <td style={{padding:"8px 10px",textAlign:"center"}}>{a.counts.planned}</td>
                      <td style={{padding:"8px 10px",textAlign:"center"}}>{a.counts.drafted}</td>
                      <td style={{padding:"8px 10px",textAlign:"center",color:"#10b981",fontWeight:600}}>{a.counts.passed}</td>
                      <td style={{padding:"8px 10px",textAlign:"center",fontWeight:700,color:a.counts.avg_grade?gradeColor(a.counts.avg_grade):"var(--dim)"}}>
                        {a.counts.avg_grade?a.counts.avg_grade.toFixed(1):"—"}
                      </td>
                      <td style={{padding:"8px 10px"}}>
                        <Link href={`/dashboard/projects/${pid}/accounts/${a.id}`} style={{fontSize:11,color:"var(--scheduled)"}}>open →</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KPI({label,value,icon,color}:{label:string;value:string;icon:string;color?:string}){
  return (
    <div className="card" style={{margin:0}}>
      <div style={{fontSize:24}}>{icon}</div>
      <p className="note" style={{margin:"4px 0 0",fontSize:11}}>{label}</p>
      <h2 style={{margin:0,fontSize:22,color:color||"inherit"}}>{value}</h2>
    </div>
  );
}
