"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

type Doc = { doc_type: string; content: string; updated_at: string };
type Post = { id: string; status: string; topic: string; created_at: string; video_url?: string; grade?: any; script?: any };
type Data = {
  account: { name: string; handle: string; niche: string; paused: boolean; posts_per_day: number; daily_budget_usd: number; project_name?: string };
  documents: Record<string, Doc>;
  posts: Post[];
  stats: { posts_count: number; published_count: number; avg_grade: number; docs_count: number };
};

const DOC_LABELS: Record<string,{label:string;icon:string}> = {
  executive_summary:  { label: "Executive Summary",    icon: "📋" },
  vision_mission:     { label: "Vision & Mission",    icon: "🎯" },
  revenue_model:      { label: "Revenue Model",       icon: "💰" },
  brand_identity:     { label: "Brand Identity",      icon: "🎨" },
  visual_identity:    { label: "Visual Identity",     icon: "🎬" },
  marketing_strategy: { label: "Marketing Strategy",  icon: "📣" },
  instagram_playbook: { label: "Instagram Playbook",  icon: "📸" },
  tiktok_playbook:    { label: "TikTok Playbook",     icon: "🎵" },
  youtube_playbook:   { label: "YouTube Playbook",    icon: "▶️" },
  content_calendar:   { label: "Content Calendar",    icon: "📅" },
  content_rules:      { label: "Content Rules",       icon: "📐" },
  hashtags_seo:       { label: "Hashtags / SEO",      icon: "🔖" },
  production_sop:     { label: "Production SOP",      icon: "⚙️" },
  business_plan:      { label: "Business Plan",       icon: "📘" },
  brand_guidelines:   { label: "Brand Guidelines",    icon: "🎨" },
  tone_guide:         { label: "Tone Guide",          icon: "🗣️" },
  visual_rules:       { label: "Visual Rules",        icon: "🎬" },
};

function StatusPill({ s }: { s: string }) {
  const color: Record<string,string> = {
    idea:"#64748b", drafted:"#a78bfa", approved:"#10b981", scheduled:"#0ea5e9",
    published:"#22c55e", rejected:"#ef4444", failed:"#dc2626", reported:"#22c55e",
  };
  return <span style={{fontSize:10,padding:"2px 8px",borderRadius:20,background:(color[s]||"#334")+"33",color:color[s]||"#fff",border:"1px solid "+(color[s]||"#334")}}>{s}</span>;
}

export default function BusinessPlan() {
  const { aid } = useParams<{ aid: string }>();
  const [d, setD] = useState<Data|null>(null);
  const [err, setErr] = useState("");
  const [active, setActive] = useState<string>("executive_summary");
  useEffect(()=>{
    fetch(`/api/business/${aid}`, { cache: "no-store" })
      .then(r=>r.ok?r.json():Promise.reject(r.statusText))
      .then(setD).catch(setErr);
  },[aid]);
  if (err) return <div className="p-8 text-red-400">Error: {err}. <Link href="/dashboard" className="underline">Back</Link></div>;
  if (!d) return <div className="p-8 text-white/60">Loading…</div>;

  const docKeys = Object.keys(DOC_LABELS).filter(k => d.documents[k]?.content);
  const activeDoc = d.documents[active] || d.documents[docKeys[0]];
  const sameBrandTone = d.documents.brand_identity?.content === d.documents.tone_guide?.content;

  return (
    <div className="p-6 max-w-6xl mx-auto text-white">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold">📘 {d.account.name}</h1>
          <p className="text-white/60 text-sm">@{d.account.handle} · {d.account.niche} {d.account.project_name?`· ${d.account.project_name}`:""}</p>
        </div>
        <Link href="/dashboard" className="text-sm px-3 py-1 rounded bg-white/10">← Dashboard</Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <Stat label="Brand Docs" value={d.stats.docs_count} />
        <Stat label="Posts" value={d.stats.posts_count} />
        <Stat label="Published" value={d.stats.published_count} />
        <Stat label="Avg Grade" value={`${d.stats.avg_grade}/10`} />
      </div>

      {sameBrandTone && (
        <div className="rounded-xl p-3 bg-yellow-500/10 border border-yellow-500/30 text-yellow-200 text-sm mb-4">
          Note: Brand Identity and Tone Guide currently share the same content. Agents treat them the same but the architect can regenerate them separately.
        </div>
      )}

      <div className="grid md:grid-cols-[220px_1fr] gap-4">
        <nav className="space-y-1">
          {docKeys.map(k => {
            const meta = DOC_LABELS[k] || {label:k, icon:"•"};
            const on = active===k;
            return (
              <button key={k} onClick={()=>setActive(k)} className={`w-full text-left px-3 py-2 rounded-lg text-sm flex items-center gap-2 ${on?"bg-white/15":"bg-white/5 hover:bg-white/10"}`}>
                <span>{meta.icon}</span><span className="truncate">{meta.label}</span>
              </button>
            );
          })}
        </nav>

        <article className="bg-white/5 rounded-2xl p-6 border border-white/10 min-h-[400px]">
          {activeDoc ? (
            <>
              <h2 className="text-xl font-semibold mb-1">
                {DOC_LABELS[active]?.icon} {DOC_LABELS[active]?.label || active}
              </h2>
              <p className="text-white/40 text-xs mb-4">Updated {new Date(activeDoc.updated_at).toLocaleString()}</p>
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-white/85">
                {activeDoc.content}
              </div>
            </>
          ) : (
            <p className="text-white/50">Document not yet written. Once the Architect finishes brand onboarding, the 13 docs will appear here.</p>
          )}
        </article>
      </div>

      <section className="mt-8">
        <h2 className="text-lg font-semibold mb-3">📱 Posts</h2>
        {d.posts.length===0 && <p className="text-white/50 text-sm">No posts yet.</p>}
        <div className="grid md:grid-cols-2 gap-3">
          {d.posts.map(p => (
            <div key={p.id} className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <p className="text-sm font-medium line-clamp-2">{p.topic}</p>
                  <p className="text-xs text-white/40 mt-1">{new Date(p.created_at).toLocaleDateString()}</p>
                </div>
                <StatusPill s={p.status} />
              </div>
              {p.grade && (
                <p className="text-xs mt-2 text-white/60">Grade: <b>{Number(p.grade.overall||0).toFixed(1)}/10</b> {p.grade.passed?"✅":"❌"}</p>
              )}
              {p.video_url && (
                <video src={p.video_url} controls className="mt-2 w-full rounded-lg" style={{maxHeight:260}} />
              )}
              {p.script && !p.video_url && (
                <div className="mt-2 text-xs text-white/50 italic line-clamp-2">
                  Hook: {p.script.hook}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Stat({label,value}:{label:string;value:any}) {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <p className="text-xs text-white/50 uppercase tracking-wide">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  );
}
