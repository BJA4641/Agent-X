"use client";
import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";

type Grade = {
  id: string; hook: number; visuals: number; pacing: number; audio: number; caption: number; cta: number;
  overall: number; passed: boolean; notes: string; fix_instruction: string; created_at: string;
};
type Doc = { id: string; doc_type: string; content: string; updated_at: string; agent: string; version: number };
type Post = {
  id: string; post_type: string; title: string; hook?: string; script?: string; caption: string;
  hashtags: string[]; status: string; duration_seconds: number; created_at: string;
  metadata?: { pillar?: string; trend_pattern?: string };
  grade?: Grade | null;
};
type MemEntry = { id: string; role: string; content: string; created_at: string };
type Account = {
  id: string; name: string; handle: string; niche: string; platforms: string[];
  status: string; avatar_emoji: string; paused: boolean; daily_budget_usd: number; posts_per_day: number;
};

// ---- Tiny markdown (no external deps) ----
const linkRe = /\[([^\]]+)\]\(([^)]+)\)/;
const codeRe = /`([^`]+)`/;
const boldRe = /\*\*([^*]+)\*\*/;

function SimpleMarkdown({ text }: { text: string }) {
  if (!text) return null;
  const lines = text.split(/\r?\n/);
  const out: JSX.Element[] = [];
  let list: JSX.Element[] | null = null;
  let listType: "ul" | "ol" | null = null;
  let table: string[][] = [];
  const flushList = () => {
    if (list && listType) {
      const Tag = listType;
      out.push(<Tag key={"l-"+out.length} style={{ paddingLeft: 22, margin: "8px 0" }}>{list}</Tag>);
      list = null; listType = null;
    }
  };
  const flushTable = () => {
    if (table.length >= 2) {
      const [header, , ...rows] = table;
      out.push(
        <table key={"t-"+out.length} style={{ borderCollapse:"collapse", width:"100%", margin:"10px 0", fontSize:13 }}>
          <thead><tr>{header.map((h,i) => <th key={i} style={{ border:"1px solid var(--line)", padding:"6px 10px", textAlign:"left", background:"var(--bg)" }}>{inline(h)}</th>)}</tr></thead>
          <tbody>{rows.map((r,ri) => <tr key={ri}>{r.map((c,i) => <td key={i} style={{ border:"1px solid var(--line)", padding:"6px 10px" }}>{inline(c)}</td>)}</tr>)}</tbody>
        </table>
      );
    }
    table = [];
  };
  function inline(s: string): React.ReactNode {
    const parts: React.ReactNode[] = [];
    let rest = s, key=0;
    while (rest) {
      const m = rest.match(linkRe);
      if (m && m.index !== undefined) {
        if (m.index > 0) parts.push(<span key={key++}>{processBoldCode(rest.slice(0, m.index))}</span>);
        parts.push(<a key={key++} href={m[2]} target="_blank" rel="noreferrer" style={{color:"var(--scheduled)"}}>{processBoldCode(m[1])}</a>);
        rest = rest.slice(m.index + m[0].length); continue;
      }
      parts.push(<span key={key++}>{processBoldCode(rest)}</span>); break;
    }
    return parts;
  }
  function processBoldCode(s: string): React.ReactNode {
    const nodes: React.ReactNode[] = [];
    let rest = s, k=0;
    while (rest) {
      const b = rest.match(boldRe), c = rest.match(codeRe);
      const bi = b?.index ?? Infinity, ci = c?.index ?? Infinity;
      if (bi < ci && b) {
        if (bi > 0) nodes.push(rest.slice(0,bi));
        nodes.push(<strong key={"b-"+(k++)} style={{color:"var(--scheduled)"}}>{b[1]}</strong>);
        rest = rest.slice(bi + b[0].length);
      } else if (c) {
        if ((c.index ?? 0) > 0) nodes.push(rest.slice(0,c.index));
        nodes.push(<code key={"c-"+(k++)} style={{background:"var(--bg)",padding:"1px 6px",borderRadius:4,fontSize:12}}>{c[1]}</code>);
        rest = rest.slice((c.index ?? 0) + c[0].length);
      } else { nodes.push(rest); break; }
    }
    return nodes;
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      flushList();
      const cells = line.trim().slice(1,-1).split("|").map(c => c.trim());
      if (cells.every(c => /^[-:]+$/.test(c))) { table.push(cells); continue; }
      table.push(cells); continue;
    } else if (table.length) { flushTable(); }
    if (!line.trim()) { flushList(); continue; }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      flushList();
      const lvl = h[1].length;
      const size = lvl===1?22:lvl===2?18:lvl===3?15:14;
      const color = lvl<=2 ? "var(--scheduled)" : undefined;
      out.push(<div key={out.length} style={{fontSize:size,fontWeight:700,marginTop:18,marginBottom:8,color}}>{inline(h[2])}</div>);
      continue;
    }
    if (line.trim() === "---") { flushList(); out.push(<hr key={out.length} style={{border:"none",borderTop:"1px solid var(--line)",margin:"12px 0"}}/>); continue; }
    const ulm = line.match(/^\s*[-*]\s+(.*)$/);
    const olm = line.match(/^\s*\d+\.\s+(.*)$/);
    if (ulm) {
      if (listType !== "ul") { flushList(); list=[]; listType="ul"; }
      list!.push(<li key={list!.length} style={{margin:"3px 0"}}>{inline(ulm[1])}</li>); continue;
    }
    if (olm) {
      if (listType !== "ol") { flushList(); list=[]; listType="ol"; }
      list!.push(<li key={list!.length} style={{margin:"3px 0"}}>{inline(olm[1])}</li>); continue;
    }
    flushList();
    out.push(<p key={out.length} style={{margin:"6px 0"}}>{inline(line)}</p>);
  }
  flushList(); flushTable();
  return <>{out}</>;
}

const TABS = [
  { key:"overview",  label:"Overview",    icon:"📋" },
  { key:"chat",      label:"Chat with agents", icon:"💬" },
  { key:"business",  label:"Business",    icon:"📘", doc:"business_plan" },
  { key:"brand",     label:"Brand",       icon:"🎨", doc:"brand_guidelines" },
  { key:"tone",      label:"Tone",        icon:"🗣️", doc:"tone_guide" },
  { key:"visuals",   label:"Visuals",     icon:"🎬", doc:"visual_rules" },
  { key:"content",   label:"Content rules", icon:"📐", doc:"content_rules" },
  { key:"posts",     label:"Posts",       icon:"📱" },
  { key:"pipeline",  label:"Live content", icon:"🎞️" },
  { key:"library",   label:"All documents", icon:"📚" },
];

const STATUS_STYLE: Record<string,{bg:string;fg:string;label:string}> = {
  planned:   {bg:"#334155", fg:"#fff", label:"planned"},
  drafted:   {bg:"#a78bfa", fg:"#000", label:"drafted"},
  approved:  {bg:"#10b981", fg:"#000", label:"approved"},
  scheduled: {bg:"#0ea5e9", fg:"#000", label:"scheduled"},
  published: {bg:"#22c55e", fg:"#000", label:"published"},
  rejected:  {bg:"#ef4444", fg:"#fff", label:"rejected"},
  failed:    {bg:"#ef4444", fg:"#fff", label:"failed"},
};

function gradeColor(n: number): string {
  if (n >= 9) return "#10b981";
  if (n >= 8) return "#22c55e";
  if (n >= 7) return "#eab308";
  if (n >= 5) return "#f97316";
  return "#ef4444";
}

function GradeBadge({ score, label, small }: { score: number; label?: string; small?: boolean }) {
  const c = gradeColor(score);
  return (
    <span title={(label||"score")+": "+score+"/10"} style={{
      fontSize: small?10:11, padding: small?"2px 6px":"3px 8px", borderRadius: 20,
      background: c+"22", color: c, border: "1px solid "+c, fontWeight: 700,
      display: "inline-flex", alignItems: "center", gap: 3,
    }}>
      {label && <span style={{fontWeight:500,opacity:.8}}>{label}</span>}
      {score}
    </span>
  );
}

export default function AccountDetailPage() {
  const params = useParams<{pid:string; aid:string}>();
  const { pid, aid } = params;
  const [docs, setDocs] = useState<Record<string,Doc>>({});
  const [posts, setPosts] = useState<Post[]>([]);
  const [account, setAccount] = useState<Account|null>(null);
  const [memory, setMemory] = useState<MemEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");
  const [chatText, setChatText] = useState("");
  const [libDoc, setLibDoc] = useState<string|null>(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [savingDoc, setSavingDoc] = useState(false);
  const [sendingChat, setSendingChat] = useState(false);
  const chatRef = useRef<HTMLDivElement>(null);

  async function refresh() {
    const r = await fetch(`/api/projects/${pid}/accounts/${aid}`, { cache: "no-store" });
    if (r.ok) {
      const j = await r.json();
      setDocs(j.documents||{});
      setPosts(j.posts||[]);
      setAccount(j.account||null);
      setMemory(j.memory||[]);
    }
    setLoading(false);
  }
  useEffect(() => { if (pid && aid) refresh(); }, [pid, aid]);
  useEffect(() => {
    if (!pid||!aid) return;
    const id = setInterval(refresh, 6000);
    return () => clearInterval(id);
  }, [pid, aid]);
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [memory, tab]);

  async function saveDoc() {
    if (!libDoc) return;
    setSavingDoc(true);
    const r = await fetch(`/api/projects/${pid}/accounts/${aid}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doc_type: libDoc, content: editText }),
    });
    setSavingDoc(false);
    if (!r.ok) { const j = await r.json().catch(()=>({})); alert(j.error || "Save failed"); return; }
    setEditing(false);
    await refresh();
  }

  function openDoc(k: string) { setTab("library"); setLibDoc(k); setEditing(false); }

  async function togglePaused() {
    if (!account) return;
    await fetch(`/api/projects/${pid}/accounts/${aid}`, {
      method:"PATCH", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ paused: !account.paused }),
    });
    refresh();
  }

  async function sendChat() {
    const text = chatText.trim();
    if (!text || sendingChat) return;
    setSendingChat(true);
    await fetch(`/api/memory`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ account_id: aid, content: text }),
    });
    setChatText("");
    setSendingChat(false);
    refresh();
  }

  const hasAllDocs = ["business_plan","brand_guidelines","tone_guide","visual_rules","content_rules"].every(d=>docs[d]);
  const activeDoc = TABS.find(t=>t.key===tab)?.doc;
  const docContent = activeDoc ? docs[activeDoc]?.content : null;

  return (
    <div>
      <div style={{ marginBottom:8 }}>
        <Link href={`/dashboard/projects/${pid}`} className="note" style={{fontSize:13}}>← Back to accounts</Link>
      </div>

      {account && (
        <div className="card" style={{padding:14, display:"flex", justifyContent:"space-between", alignItems:"center", gap:12, flexWrap:"wrap", borderColor: account.paused?"#ef4444":undefined }}>
          <div style={{display:"flex", alignItems:"center", gap:12}}>
            <span style={{fontSize:36}}>{account.avatar_emoji}</span>
            <div>
              <h2 style={{margin:0}}>{account.name}</h2>
              <p className="note" style={{margin:0}}>
                @{account.handle} · {account.niche.replace(/_/g," ")} · {account.platforms.join(", ")}
                {account.paused && <span style={{color:"#ef4444", marginLeft:8, fontWeight:700}}>⏸ PAUSED</span>}
              </p>
            </div>
          </div>
          <button onClick={togglePaused}
                  style={{background: account.paused ? "#10b981" : "#ef4444", border:"none", padding:"10px 18px"}}>
            {account.paused ? "▶ Resume this account" : "⏸ Pause this account"}
          </button>
        </div>
      )}

      {loading ? <p className="note">Loading…</p> : !hasAllDocs && posts.length===0 ? (
        <div className="card" style={{borderColor:"#f59e0b",background:"rgba(245,158,11,0.08)",marginTop:12}}>
          <b>⏳ Agents are building this account…</b>
          <p className="note" style={{margin:"8px 0 0"}}>
            The Architect is writing the business plan, brand kit, tone, visuals, and content rules.
            Then the Strategist plans 10 kickoff posts. The Grader will score every draft and force
            rewrites until each post averages 8/10 or higher. Refresh in a minute.
          </p>
        </div>
      ) : null}

      {/* Tabs */}
      <div style={{display:"flex", gap:6, flexWrap:"wrap", margin:"20px 0 16px", borderBottom:"1px solid var(--line)", paddingBottom:8}}>
        {TABS.map(t => {
          const ready = t.doc ? !!docs[t.doc] : true;
          return (
            <button key={t.key} onClick={()=>setTab(t.key)}
              style={{
                padding:"8px 14px", borderRadius:10, cursor:"pointer", fontSize:13,
                border:"1px solid "+(tab===t.key?"var(--scheduled)":"var(--line)"),
                background: tab===t.key?"var(--scheduled)":"transparent",
                color: tab===t.key?"#000":"inherit", fontWeight: tab===t.key?600:400,
                opacity: ready?1:0.5,
              }}>
              <span style={{marginRight:6}}>{t.icon}</span>{t.label}
              {t.key==="posts" && posts.length>0 && <span style={{marginLeft:6,fontSize:11,opacity:.7}}>({posts.length})</span>}
              {t.key==="chat" && memory.filter(m=>m.role==="user").length>0 && <span style={{marginLeft:6,fontSize:11,opacity:.7}}>({memory.filter(m=>m.role==="user").length})</span>}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab==="overview" && (<>
        <Overview docs={docs} posts={posts} account={account} onOpenDoc={openDoc} />
        <CloneBox pid={pid as string} aid={aid as string} />
      </>)}
      {tab==="library" && (
        <DocLibrary docs={docs} libDoc={libDoc} setLibDoc={(k)=>{setLibDoc(k);setEditing(false);}}
                    editing={editing} setEditing={setEditing}
                    editText={editText} setEditText={setEditText}
                    saveDoc={saveDoc} saving={savingDoc} />
      )}
      {tab==="chat" && <ChatPanel memory={memory} chatText={chatText} setChatText={setChatText}
                                  sendChat={sendChat} sendingChat={sendingChat} chatRef={chatRef} />}
      {docContent && (
        <div className="card" style={{maxWidth:800}}>
          <div className="markdown" style={{fontSize:14,lineHeight:1.7}}>
            <SimpleMarkdown text={docContent} />
          </div>
          <p className="note" style={{fontSize:11,marginTop:16}}>
            Written by <b>{docs[activeDoc!]?.agent}</b> · v{docs[activeDoc!]?.version} · updated {new Date(docs[activeDoc!]?.updated_at||"").toLocaleString()}
          </p>
        </div>
      )}
      {tab==="posts" && <PostsGrid posts={posts} />}
      {tab==="pipeline" && <PipelineTab pid={pid} aid={aid} />}

      <style>{`
        .markdown h1{font-size:22px;margin:18px 0 10px;}
        .markdown h2{font-size:18px;margin:16px 0 8px;color:var(--scheduled);}
        .markdown h3{font-size:15px;margin:14px 0 6px;}
        .markdown p{margin:6px 0;}
        .markdown ul,.markdown ol{margin:6px 0;padding-left:22px;}
        .markdown li{margin:3px 0;}
        .markdown code{background:var(--bg);padding:1px 6px;border-radius:4px;font-size:12px;}
        .markdown table{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px;}
        .markdown th,.markdown td{border:1px solid var(--line);padding:6px 10px;text-align:left;}
        .markdown th{background:var(--bg);}
        .markdown strong{color:var(--scheduled);}
      `}</style>
    </div>
  );
}

function Overview({ docs, posts, account, onOpenDoc }: { docs:Record<string,Doc>; posts:Post[]; account:Account|null; onOpenDoc:(k:string)=>void }) {
  const ready = Object.keys(docs).length;
  const avgGrade = posts.filter(p=>p.grade).reduce((s,p)=>s+(p.grade?.overall||0),0) / Math.max(1, posts.filter(p=>p.grade).length);
  const passedCount = posts.filter(p=>p.grade?.passed).length;
  return (
    <div>
      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12,marginBottom:20}}>
        <InfoCard label="Documents" value={`${ready}/5`} icon="📄" />
        <InfoCard label="Posts planned" value={String(posts.length)} icon="📱" />
        <InfoCard label="Avg grade" value={posts.some(p=>p.grade) ? avgGrade.toFixed(1)+"/10" : "—"} icon="🎯" />
        <InfoCard label="Passed (≥8)" value={String(passedCount)} icon="✅" />
        <InfoCard label="Status" value={ready>=5?"ready":"building…"} icon={ready>=5?"✅":"⏳"} />
      </div>

      <div className="card" style={{maxWidth:800}}>
        <h3>Brand kit progress</h3>
        <ul style={{paddingLeft:20,fontSize:14,lineHeight:1.9,margin:"10px 0"}}>
          {(["business_plan","brand_guidelines","tone_guide","visual_rules","content_rules"] as const).map(k=>{
            const label:any = { business_plan:"📘 Business plan", brand_guidelines:"🎨 Brand guidelines",
                              tone_guide:"🗣️ Tone guide", visual_rules:"🎬 Visual rules", content_rules:"📐 Content rules" }[k];
            return (
              <li key={k}>
                {docs[k] ? (
                  <button onClick={()=>onOpenDoc(k)}
                    style={{background:"none",border:"none",color:"inherit",cursor:"pointer",padding:0,font:"inherit",textDecoration:"underline",textUnderlineOffset:3}}>
                    {label}
                  </button>
                ) : label} — {docs[k]?"✅ written · click to open":"⏳ pending…"}
              </li>
            );
          })}
        </ul>
        {Object.keys(docs).length > 5 && (
          <p className="note" style={{fontSize:12,margin:"4px 0 0"}}>
            + {Object.keys(docs).length - 5} more documents (revenue model, playbooks, strategy…) in the <b>📚 All documents</b> tab.
          </p>
        )}
      </div>

      {account?.paused && (
        <div className="card" style={{borderColor:"#ef4444",background:"rgba(239,68,68,0.08)",marginTop:12}}>
          <b>⏸ This account is PAUSED</b>
          <p className="note" style={{margin:"4px 0 0"}}>
            Agents will not work on it until you hit "Resume".
          </p>
        </div>
      )}

      {posts.some(p=>p.grade) && (
        <div className="card" style={{marginTop:14,maxWidth:800}}>
          <h3>Latest graded posts</h3>
          <div style={{display:"grid",gap:10,marginTop:10}}>
            {posts.filter(p=>p.grade).slice(0,3).map(p=>(
              <div key={p.id} style={{padding:10,border:"1px solid var(--line)",borderRadius:10}}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:8}}>
                  <b style={{fontSize:13}}>{p.title}</b>
                  <GradeBadge score={p.grade!.overall} />
                </div>
                <div style={{display:"flex",gap:5,flexWrap:"wrap",marginTop:6}}>
                  <GradeBadge score={p.grade!.hook} label="hook" small />
                  <GradeBadge score={p.grade!.visuals} label="visuals" small />
                  <GradeBadge score={p.grade!.pacing} label="pacing" small />
                  <GradeBadge score={p.grade!.audio} label="audio" small />
                  <GradeBadge score={p.grade!.caption} label="caption" small />
                  <GradeBadge score={p.grade!.cta} label="CTA" small />
                </div>
                {p.grade!.fix_instruction && p.grade!.fix_instruction !== "publish" && (
                  <p className="note" style={{fontSize:11,margin:"6px 0 0",color:"#f97316"}}>
                    <b>Fix:</b> {p.grade!.fix_instruction}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DocLibrary({ docs, libDoc, setLibDoc, editing, setEditing, editText, setEditText, saveDoc, saving }: {
  docs: Record<string,Doc>; libDoc: string|null; setLibDoc:(k:string)=>void;
  editing: boolean; setEditing:(b:boolean)=>void;
  editText: string; setEditText:(t:string)=>void;
  saveDoc: ()=>void; saving: boolean;
}) {
  const keys = Object.keys(docs).sort();
  const pretty = (k:string) => k.replace(/_/g," ").replace(/\b\w/g, c=>c.toUpperCase());
  const cur = libDoc ? docs[libDoc] : null;
  if (keys.length === 0) return (
    <p className="note" style={{padding:30,textAlign:"center"}}>
      No documents yet. The Architect writes the full kit automatically when this account becomes active.
    </p>
  );
  return (
    <div style={{display:"grid",gridTemplateColumns:"230px 1fr",gap:14,alignItems:"start"}}>
      <div className="card" style={{padding:8,position:"sticky",top:10}}>
        {keys.map(k => (
          <button key={k} onClick={()=>setLibDoc(k)}
            style={{display:"block",width:"100%",textAlign:"left",padding:"8px 10px",borderRadius:8,cursor:"pointer",
                    fontSize:13, border:"1px solid "+(libDoc===k?"var(--scheduled)":"transparent"),
                    background: libDoc===k?"var(--scheduled)":"transparent",
                    color: libDoc===k?"#000":"inherit", fontWeight: libDoc===k?600:400, marginBottom:2}}>
            {pretty(k)}
          </button>
        ))}
      </div>
      <div className="card" style={{minHeight:200}}>
        {!cur ? (
          <p className="note" style={{padding:20}}>Pick a document on the left to read or edit it.</p>
        ) : editing ? (
          <div>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
              <b>{pretty(libDoc!)} — editing</b>
              <span style={{display:"flex",gap:8}}>
                <button className="ghost" onClick={()=>setEditing(false)} disabled={saving}>Cancel</button>
                <button className="primary" onClick={saveDoc} disabled={saving}>{saving?"Saving…":"Save"}</button>
              </span>
            </div>
            <textarea value={editText} onChange={e=>setEditText(e.target.value)}
              style={{width:"100%",minHeight:420,fontFamily:"var(--font-mono)",fontSize:13,lineHeight:1.6,
                      background:"var(--bg)",color:"inherit",border:"1px solid var(--line)",borderRadius:10,padding:12}} />
            <p className="note" style={{fontSize:11,marginTop:8}}>
              Markdown supported. Agents read this document when writing every script for this account —
              your edits change their behavior from the next job onward.
            </p>
          </div>
        ) : (
          <div>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
              <b>{pretty(libDoc!)}</b>
              <button className="ghost" onClick={()=>{setEditText(cur.content||"");setEditing(true);}}>✏️ Edit</button>
            </div>
            <div className="markdown" style={{fontSize:14,lineHeight:1.7}}>
              <SimpleMarkdown text={cur.content||""} />
            </div>
            <p className="note" style={{fontSize:11,marginTop:16}}>
              Written by <b>{cur.agent}</b> · v{cur.version} · updated {new Date(cur.updated_at||"").toLocaleString()}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ChatPanel({ memory, chatText, setChatText, sendChat, sendingChat, chatRef }: any) {
  const ROLE_ICON: Record<string,string> = { user:"🧑‍💻", architect:"🏛️", strategist:"📊", brain:"🧠",
                                             qa:"🔍", grader:"🎯", visuals:"🎨", system:"⚙️" };
  const ROLE_COLOR: Record<string,string> = { user:"var(--scheduled)", architect:"#a78bfa", strategist:"#f59e0b",
                                              brain:"#22d3ee", qa:"#06b6d4", grader:"#ef4444", visuals:"#ec4899",
                                              system:"var(--dim)" };
  return (
    <div>
      <div className="card" style={{maxWidth:800,padding:0,overflow:"hidden"}}>
        <div ref={chatRef} style={{height:380, overflowY:"auto", padding:14, background:"var(--bg)"}}>
          {memory.length===0 ? (
            <p className="note" style={{textAlign:"center",padding:40}}>
              Give your agents instructions. They'll see these notes while building this account
              and when writing every script. Example: "use deadpan humor, reference tools I list,
              no fake gurus".
            </p>
          ) : memory.map((m:MemEntry) => {
            const isUser = m.role==="user";
            return (
              <div key={m.id} style={{marginBottom:10, display:"flex", gap:8,
                                       justifyContent: isUser?"flex-end":"flex-start"}}>
                {!isUser && <span style={{fontSize:20}}>{ROLE_ICON[m.role]||"🤖"}</span>}
                <div style={{maxWidth:"78%", padding:"8px 12px", borderRadius:12,
                            background: isUser?ROLE_COLOR.user+"22":"var(--card, #1a1a1a)",
                            border:"1px solid "+(isUser?"var(--scheduled)":"var(--line)"),
                            fontSize:13}}>
                  <div style={{fontSize:10,opacity:.6,marginBottom:3,
                               color:isUser?"var(--scheduled)":ROLE_COLOR[m.role]||"inherit"}}>
                    {m.role.toUpperCase()} · {new Date(m.created_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})}
                  </div>
                  {m.content}
                </div>
                {isUser && <span style={{fontSize:20}}>{ROLE_ICON.user}</span>}
              </div>
            );
          })}
        </div>
        <div style={{display:"flex",gap:8,padding:10,borderTop:"1px solid var(--line)"}}>
          <input
            value={chatText}
            onChange={e=>setChatText(e.target.value)}
            onKeyDown={e=>{if(e.key==="Enter" && !e.shiftKey){e.preventDefault();sendChat();}}}
            placeholder='Tell your agents what to do (e.g. "use more sarcasm, no stock photos")'
            style={{flex:1,background:"var(--bg)",border:"1px solid var(--line)",borderRadius:8,padding:"10px 12px",color:"inherit",fontSize:13}}/>
          <button onClick={sendChat} disabled={sendingChat||!chatText.trim()}>
            {sendingChat?"…":"Send →"}
          </button>
        </div>
      </div>
      <p className="note" style={{fontSize:11,maxWidth:800,marginTop:8}}>
        💡 Agents read your recent messages before every task (architect writes brand docs,
        strategist plans posts, brain writes scripts, grader scores them). Memory persists,
        so your instructions stick forever.
      </p>
    </div>
  );
}

function InfoCard({label, value, icon}:{label:string;value:string;icon:string}) {
  return (
    <div className="card" style={{margin:0}}>
      <div style={{fontSize:28}}>{icon}</div>
      <p className="note" style={{margin:"4px 0 0"}}>{label}</p>
      <h2 style={{margin:0,fontSize:22}}>{value}</h2>
    </div>
  );
}

function PostsGrid({ posts }:{ posts:Post[] }) {
  if (posts.length === 0) {
    return <div className="card"><p className="note">No posts yet. Strategist will plan 10 kickoff posts once brand docs are ready.</p></div>;
  }
  return (
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(340px,1fr))",gap:14}}>
      {posts.map((p,i)=>{
        const st = STATUS_STYLE[p.status] || STATUS_STYLE.planned;
        const g = p.grade;
        return (
          <div key={p.id} className="card" style={{margin:0}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",gap:8,flexWrap:"wrap"}}>
              <span style={{fontSize:11,padding:"3px 8px",borderRadius:20,background:st.bg,color:st.fg,fontWeight:600}}>
                {st.label}
              </span>
              <span className="note" style={{fontSize:11}}>{p.post_type} · {p.duration_seconds}s</span>
              {g && <GradeBadge score={g.overall} />}
            </div>
            <h4 style={{margin:"10px 0 6px"}}>{p.title}</h4>
            {p.hook && <p style={{fontSize:15,fontWeight:600,color:"var(--approved)",margin:"6px 0"}}>"{p.hook}"</p>}
            {p.script && <p className="note" style={{fontSize:12,maxHeight:60,overflow:"hidden",margin:"6px 0"}}>{p.script.slice(0,160)}{p.script.length>160?"…":""}</p>}
            {g && (
              <div style={{display:"flex",gap:4,flexWrap:"wrap",margin:"8px 0"}}>
                <GradeBadge score={g.hook} label="H" small />
                <GradeBadge score={g.visuals} label="V" small />
                <GradeBadge score={g.pacing} label="P" small />
                <GradeBadge score={g.audio} label="A" small />
                <GradeBadge score={g.caption} label="C" small />
                <GradeBadge score={g.cta} label="CTA" small />
              </div>
            )}
            {g && !g.passed && g.fix_instruction !== "publish" && (
              <p style={{fontSize:11,color:"#f97316",margin:"6px 0",padding:6,background:"#f9731622",borderRadius:6}}>
                🔁 Rewriting: {g.fix_instruction.slice(0,120)}
              </p>
            )}
            {p.caption && <p style={{fontSize:12,color:"var(--dim)",marginTop:6}}>{p.caption.slice(0,140)}{p.caption.length>140?"…":""}</p>}
            {p.hashtags?.length>0 && (
              <div style={{display:"flex",flexWrap:"wrap",gap:4,marginTop:8}}>
                {p.hashtags.slice(0,8).map((h:string)=>(
                  <span key={h} style={{fontSize:11,padding:"2px 7px",borderRadius:10,background:"var(--bg)",border:"1px solid var(--line)",color:"var(--scheduled)"}}>#{h}</span>
                ))}
              </div>
            )}
            <p className="note" style={{fontSize:10,marginTop:8}}>#{i+1} · pillar: {p.metadata?.pillar||p.post_type} {p.metadata?.trend_pattern && `· trend: ${p.metadata.trend_pattern}`}</p>
          </div>
        );
      })}
    </div>
  );
}


// v5.8 BATCH4 — Clone a trending post (angle-clone, never a repost)
function CloneBox({ pid, aid }: { pid: string; aid: string }) {
  const [url, setUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [format, setFormat] = useState<"reel"|"carousel">("reel");
  const [state, setState] = useState<"idle"|"busy"|"done"|"err">("idle");
  const [msg, setMsg] = useState("");
  async function submit() {
    setState("busy"); setMsg("");
    const r = await fetch(`/api/projects/${pid}/accounts/${aid}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "clone_post", source_url: url, notes, format }),
    });
    const j = await r.json();
    if (j.ok) { setState("done"); setMsg(`Queued as a ${j.format} — the writers pick it up within a tick. Watch it in Studio.`); setUrl(""); setNotes(""); }
    else { setState("err"); setMsg(j.error || "failed"); }
  }
  return (
    <div className="card" style={{ maxWidth: 720, marginTop: 16 }}>
      <h3 style={{ marginTop: 0 }}>🎯 Clone a trending post</h3>
      <p className="note">
        Paste the link, then <b>describe what the post is</b> — Instagram login-walls its pages, so the
        agents can't read the URL; your description is the brief. They recreate the <b>angle</b> as an
        original script in this account's brand voice. Never a repost (reposts don't monetize — Content
        ID pays the original creator).
      </p>
      <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.instagram.com/reel/… (optional, kept for reference)"
             style={{ width: "100%", marginBottom: 8 }} />
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
                placeholder='What is it? e.g. "7-slide carousel: 5 morning skincare mistakes, bold red text on beige, very fast hook"'
                style={{ width: "100%", marginBottom: 8 }} />
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <select value={format} onChange={(e) => setFormat(e.target.value as any)}>
          <option value="reel">Make it a reel</option>
          <option value="carousel">Make it a carousel</option>
        </select>
        <button onClick={submit} disabled={state === "busy" || notes.trim().length < 10}>
          {state === "busy" ? "Queuing…" : "Send to the agents"}
        </button>
      </div>
      {msg && <p className="note" style={{ color: state === "err" ? "#e5484d" : "var(--approved)", marginTop: 8 }}>{msg}</p>}
    </div>
  );
}

/* ── v5.11.23 REQ-ACCOUNT-PIPELINE (DEC-076) ─────────────────────────────
   "Posts" reads account_posts (kickoff planner); the agents actually work in
   board_items. This tab is the account-scoped Studio: the same live items,
   the same approve/reject transition, filtered to THIS account — so owners
   can review content without leaving the project. */
function PipelineTab({ pid, aid }: { pid: string; aid: string }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string>("");
  const [err, setErr] = useState("");

  const load = async () => {
    try {
      const r = await fetch(`/api/projects/${pid}/accounts/${aid}/pipeline`);
      const j = await r.json();
      if (j.ok) { setItems(j.items || []); setErr(""); }
      else setErr(j.error || "load failed");
    } catch (e: any) { setErr(String(e?.message || e)); }
    setLoading(false);
  };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [pid, aid]);

  const act = async (itemId: string, action: "approve" | "reject") => {
    let reason: string | undefined;
    if (action === "reject") {
      reason = window.prompt("Why reject? (the agents read this and avoid the mistake)") || undefined;
      if (reason === undefined) return; // cancelled
    }
    setBusy(itemId);
    try {
      const r = await fetch(`/api/projects/${pid}/accounts/${aid}/pipeline`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, itemId, reason }),
      });
      const j = await r.json();
      if (!j.ok) alert(j.error || "failed");
    } catch (e: any) { alert(String(e?.message || e)); }
    setBusy(""); load();
  };

  if (loading) return <p className="note">Loading live content…</p>;
  if (err) return <div className="card"><p className="note">⚠️ {err}</p></div>;
  if (items.length === 0) return (
    <div className="card"><p className="note">
      Nothing in the pipeline for this account yet. When agents draft a reel or
      carousel it appears here the moment it exists — drafts can be approved or
      rejected right on this page.
    </p></div>
  );

  const order: Record<string, number> = { drafted: 0, idea: 1, approved: 2, scheduled: 3, quarantined: 4, published: 5 };
  const sorted = [...items].sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px,1fr))", gap: 14 }}>
      {sorted.map((it) => {
        const st = STATUS_STYLE[it.status] || { bg: "#334155", fg: "#fff", label: it.status };
        return (
          <div key={it.id} className="card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 20, background: st.bg, color: st.fg, fontWeight: 600 }}>
                {st.label}{it.dry_run_only ? " · dry-run" : ""}
              </span>
              <span className="note" style={{ fontSize: 11 }}>
                {it.format} · {new Date(it.created_at).toLocaleString()}
              </span>
            </div>
            <h4 style={{ margin: "10px 0 6px" }}>{it.topic}</h4>
            {it.images.length > 0 && (
              <div style={{ display: "flex", gap: 4, overflowX: "auto", margin: "6px 0" }}>
                {it.images.map((u: string, i: number) => (
                  <img key={i} src={u} alt="" style={{ height: 96, borderRadius: 6, flex: "0 0 auto" }} />
                ))}
              </div>
            )}
            {it.hook && <p style={{ fontSize: 13, margin: "4px 0" }}><b>Hook:</b> {it.hook}</p>}
            {it.caption && <p className="note" style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>{it.caption.slice(0, 220)}</p>}
            {it.status === "drafted" && (
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button className="btn" disabled={busy === it.id} onClick={() => act(it.id, "approve")}
                  style={{ background: "#10b981", color: "#000", fontWeight: 600 }}>Approve</button>
                <button className="btn" disabled={busy === it.id} onClick={() => act(it.id, "reject")}>Reject</button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
