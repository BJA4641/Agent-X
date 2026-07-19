"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

type Project = {
  id: string; name: string; niche: string; platforms: string[]; status: string;
  created_at: string; cta?: string; paused: boolean; daily_budget_usd: number;
};

const NICHE_EMOJI: Record<string,string> = {
  ai_tools:"🤖",finance:"💰",make_money_online:"🤑",fitness:"💪",weight_loss:"⚖️",
  skincare:"✨",men_style:"👔",cooking:"🍳",home_hacks:"🏠",pets:"🐾",travel:"✈️",
  saas:"🚀",ecommerce:"🛒",coding:"💻",psychology:"🧠",productivity:"⚡",dating:"❤️",
  gaming:"🎮",real_estate:"🏘️",luxury:"💎",motivation:"🔥",
};

const NICHE_LABEL: Record<string,string> = {
  ai_tools:"AI tools", finance:"Finance", make_money_online:"Make money online",
  fitness:"Fitness", weight_loss:"Weight loss", skincare:"Skincare",
  men_style:"Men's style", cooking:"Cooking", home_hacks:"Home hacks",
  pets:"Pets", travel:"Travel", saas:"SaaS / startups", ecommerce:"Ecommerce",
  coding:"Coding / dev", psychology:"Psychology", productivity:"Productivity",
  dating:"Dating / relationships", gaming:"Gaming", real_estate:"Real estate",
  luxury:"Luxury", motivation:"Motivation",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [niche, setNiche] = useState("ai_tools");
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string|null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    const r = await fetch("/api/projects", { cache: "no-store" });
    const j = await r.json();
    setProjects(j.projects||[]);
    setLoading(false);
  }
  useEffect(()=>{refresh();},[]);

  async function add() {
    if(!name.trim()) return;
    await fetch("/api/projects",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body: JSON.stringify({name:name.trim(), niche}),
    });
    setName("");
    refresh();
  }
  async function remove(id:string){
    if(!confirm("Delete this project and all its accounts/posts?")) return;
    await fetch("/api/projects?id="+id,{method:"DELETE"});
    refresh();
  }
  async function togglePaused(p:Project) {
    await fetch("/api/projects",{
      method:"PATCH",headers:{"Content-Type":"application/json"},
      body: JSON.stringify({id:p.id, paused:!p.paused}),
    });
    refresh();
  }
  async function seedDemo(){
    setSeeding(true); setSeedMsg(null);
    const r = await fetch("/api/admin/seed-demo",{method:"POST"});
    const j = await r.json();
    setSeeding(false);
    setSeedMsg(j.error?("Error: "+j.error)
      :`Created ${j.projects_created} projects and ${j.accounts_created} accounts. All accounts start PAUSED except the first one (AI Tool Daily) so you can start there.`);
    refresh();
  }

  return (
    <div>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:16,flexWrap:"wrap"}}>
        <div>
          <h1 style={{margin:0}}>Projects</h1>
          <p className="lead" style={{maxWidth:640}}>
            Run multiple brands/niches from one dashboard. Each project holds several
            brand accounts, each with its own business plan, brand kit, tone, visuals,
            and a queue of posts — all run by agents with an 8/10 quality gate.
          </p>
        </div>
        <button onClick={seedDemo} disabled={seeding} style={{background:"var(--scheduled)"}}>
          {seeding?"Seeding…":"🎬 Seed demo (21 niches × 5 accounts)"}
        </button>
      </div>

      {seedMsg && (
        <div className="card" style={{margin:"16px 0",borderColor:"var(--approved)",background:"rgba(16,185,129,0.08)"}}>
          {seedMsg}
        </div>
      )}

      <div className="card" style={{marginTop:16,borderColor:"#f59e0b",background:"rgba(245,158,11,0.08)"}}>
        <b>⚠️ How to use this (start small)</b>
        <ol style={{margin:"8px 0 0 18px",padding:0,fontSize:13,lineHeight:1.7}}>
          <li>Seed the demo, then open <b>AI Tools Portfolio → AI Tool Daily</b>.</li>
          <li>All other 104 accounts start <b>PAUSED</b>. Agents only work on AI Tool Daily.</li>
          <li>Use the <b>Chat with agents</b> tab to give instructions (tone, style, what to promote).</li>
          <li>Wait for posts to score <b>≥ 8/10</b> before approving. Grader auto-rewrites weak ones.</li>
          <li>When the first account looks post-worthy, resume one more. Never run all 105 at once (cost + quality).</li>
        </ol>
      </div>

      {loading?<p className="note">Loading…</p>:projects.length===0?(
        <div className="card"><p className="note">No projects yet. Create one below or hit the seed button.</p></div>
      ):(
        <div className="grid3" style={{marginTop:24}}>
          {projects.map(p=>{
            const em = NICHE_EMOJI[p.niche]||"📁";
            const label = NICHE_LABEL[p.niche]||p.niche;
            return (
              <div key={p.id} className="card" style={{
                borderColor: p.paused?"#ef444466":undefined,
                opacity: p.paused?0.6:1,
              }}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
                  <h3 style={{margin:0}}><span style={{marginRight:8}}>{em}</span>{p.name}</h3>
                  <span className="tag" style={{
                    background: p.paused?"#ef4444":"var(--approved)",
                    color:"#fff",
                  }}>{p.paused?"⏸ PAUSED":"active"}</span>
                </div>
                <p className="note" style={{margin:"8px 0"}}>{label} · {p.platforms.length} platforms · ${p.daily_budget_usd.toFixed(2)}/day</p>
                {p.cta && <p style={{fontSize:12,color:"var(--dim)"}}>CTA: {p.cta}</p>}
                <div style={{display:"flex",gap:10,marginTop:10,flexWrap:"wrap",alignItems:"center"}}>
                  <Link href={`/dashboard/projects/${p.id}`} style={{color:"var(--scheduled)",fontSize:13}}>Open accounts →</Link>
                  <button onClick={()=>togglePaused(p)}
                          style={{fontSize:11,padding:"4px 10px",borderRadius:6,cursor:"pointer",
                                  background:p.paused?"#10b98122":"#ef444422",
                                  color:p.paused?"#10b981":"#ef4444",
                                  border:"1px solid "+(p.paused?"#10b981":"#ef4444")}}>
                    {p.paused?"▶ Resume":"⏸ Pause"}
                  </button>
                  <button onClick={()=>remove(p.id)} style={{color:"var(--failed)",fontSize:12,background:"none",border:"none",cursor:"pointer"}}>delete</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="card" style={{marginTop:32,maxWidth:480}}>
        <h3>Start a new project</h3>
        <div style={{display:"grid",gap:10,marginTop:10}}>
          <input placeholder="Project/brand name (e.g. Cat Care HQ)" value={name} onChange={(e)=>setName(e.target.value)}
            style={{background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit"}}/>
          <select value={niche} onChange={(e)=>setNiche(e.target.value)}
            style={{background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit"}}>
            {Object.keys(NICHE_LABEL).map(k=>(
              <option key={k} value={k}>{NICHE_EMOJI[k]} {NICHE_LABEL[k]}</option>
            ))}
          </select>
          <button onClick={add}>Create project</button>
        </div>
      </div>
    </div>
  );
}
