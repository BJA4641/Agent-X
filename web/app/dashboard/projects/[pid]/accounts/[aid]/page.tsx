"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";

type Doc = { id: string; doc_type: string; content: string; updated_at: string; agent: string; version: number };
type Post = { id: string; post_type: string; title: string; hook?: string; script?: string; caption: string; hashtags: string[];
             status: string; duration_seconds: number; created_at: string; metadata?: { pillar?: string } };

const TABS: { key: string; label: string; icon: string; doc?: string }[] = [
  { key: "overview",    label: "Overview",    icon: "📋" },
  { key: "business",    label: "Business plan", icon: "📘", doc: "business_plan" },
  { key: "brand",       label: "Brand",       icon: "🎨", doc: "brand_guidelines" },
  { key: "tone",        label: "Tone",        icon: "🗣️", doc: "tone_guide" },
  { key: "visuals",     label: "Visuals",     icon: "🎬", doc: "visual_rules" },
  { key: "content",     label: "Content rules", icon: "📐", doc: "content_rules" },
  { key: "posts",       label: "Posts",       icon: "📱" },
];

const STATUS_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  planned:   { bg: "#334155", fg: "#fff", label: "planned" },
  drafted:   { bg: "#a78bfa", fg: "#000", label: "drafted" },
  approved:  { bg: "#10b981", fg: "#000", label: "approved" },
  scheduled: { bg: "#0ea5e9", fg: "#000", label: "scheduled" },
  published: { bg: "#22c55e", fg: "#000", label: "published" },
  rejected:  { bg: "#ef4444", fg: "#fff", label: "rejected" },
};

export default function AccountDetailPage() {
  const params = useParams<{ pid: string; aid: string }>();
  const { pid, aid } = params;
  const [docs, setDocs] = useState<Record<string, Doc>>({});
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");

  async function refresh() {
    const r = await fetch(`/api/projects/${pid}/accounts/${aid}`, { cache: "no-store" });
    if (r.ok) {
      const j = await r.json();
      setDocs(j.documents || {});
      setPosts(j.posts || []);
    }
    setLoading(false);
  }
  useEffect(() => { if (pid && aid) refresh(); }, [pid, aid]);
  useEffect(() => {
    if (!pid || !aid) return;
    const id = setInterval(refresh, 6000);
    return () => clearInterval(id);
  }, [pid, aid]);

  const hasAllDocs = ["business_plan","brand_guidelines","tone_guide","visual_rules","content_rules"].every(d => docs[d]);
  const activeDoc = TABS.find(t => t.key === tab)?.doc;
  const docContent = activeDoc ? docs[activeDoc]?.content : null;

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Link href={`/dashboard/projects/${pid}`} className="note" style={{ fontSize: 13 }}>← Back to accounts</Link>
      </div>

      {loading ? <p className="note">Loading…</p> : !hasAllDocs && posts.length === 0 ? (
        <div className="card" style={{ borderColor: "#f59e0b", background: "rgba(245,158,11,0.08)" }}>
          <b>⏳ Agents are building this account…</b>
          <p className="note" style={{ margin: "8px 0 0" }}>
            The Architect is writing the business plan, brand kit, tone guide, visual rules, and
            content rules. Then the Strategist will plan 10 kickoff posts. Refresh in a minute.
          </p>
        </div>
      ) : null}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "20px 0 16px", borderBottom: "1px solid var(--line)", paddingBottom: 8 }}>
        {TABS.map(t => {
          const ready = t.doc ? !!docs[t.doc] : true;
          return (
            <button key={t.key} onClick={()=>setTab(t.key)}
              style={{
                padding: "8px 14px", borderRadius: 10, cursor: "pointer", fontSize: 13,
                border: "1px solid " + (tab===t.key ? "var(--scheduled)" : "var(--line)"),
                background: tab===t.key ? "var(--scheduled)" : "transparent",
                color: tab===t.key ? "#000" : "inherit", fontWeight: tab===t.key ? 600 : 400,
                opacity: ready ? 1 : 0.5,
              }}>
              <span style={{ marginRight: 6 }}>{t.icon}</span>{t.label}
              {t.key === "posts" && posts.length > 0 && <span style={{marginLeft:6, fontSize:11, opacity:.7}}>({posts.length})</span>}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab === "overview" && <Overview docs={docs} posts={posts} />}
      {docContent && (
        <div className="card" style={{ maxWidth: 800 }}>
          <div className="markdown" style={{ fontSize: 14, lineHeight: 1.7 }}>
            <ReactMarkdown>{docContent}</ReactMarkdown>
          </div>
          <p className="note" style={{ fontSize: 11, marginTop: 16 }}>
            Written by <b>{docs[activeDoc!]?.agent}</b> · v{docs[activeDoc!]?.version} · updated {new Date(docs[activeDoc!]?.updated_at || "").toLocaleString()}
          </p>
        </div>
      )}
      {tab === "posts" && <PostsGrid posts={posts} />}

      <style>{`
        .markdown h1 { font-size: 22px; margin: 18px 0 10px; }
        .markdown h2 { font-size: 18px; margin: 16px 0 8px; color: var(--scheduled); }
        .markdown h3 { font-size: 15px; margin: 14px 0 6px; }
        .markdown p  { margin: 6px 0; }
        .markdown ul, .markdown ol { margin: 6px 0; padding-left: 22px; }
        .markdown li { margin: 3px 0; }
        .markdown code { background: var(--bg); padding: 1px 6px; border-radius: 4px; font-size: 12px; }
        .markdown table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 13px; }
        .markdown th, .markdown td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; }
        .markdown th { background: var(--bg); }
        .markdown strong { color: var(--scheduled); }
      `}</style>
    </div>
  );
}

function Overview({ docs, posts }: { docs: Record<string, Doc>; posts: Post[] }) {
  const ready = Object.keys(docs).length;
  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12, marginBottom: 20 }}>
        <InfoCard label="Documents ready" value={`${ready}/5`} icon="📄" />
        <InfoCard label="Posts planned" value={String(posts.length)} icon="📱" />
        <InfoCard label="Status" value={ready>=5 ? "ready" : "architecting"} icon={ready>=5 ? "✅" : "⏳"} />
      </div>
      <div className="card" style={{ maxWidth: 800 }}>
        <h3>Brand kit progress</h3>
        <ul style={{ paddingLeft: 20, fontSize: 14, lineHeight: 1.9 }}>
          {(["business_plan","brand_guidelines","tone_guide","visual_rules","content_rules"] as const).map(k => {
            const label = { business_plan: "📘 Business plan", brand_guidelines: "🎨 Brand guidelines",
                            tone_guide: "🗣️ Tone guide", visual_rules: "🎬 Visual rules",
                            content_rules: "📐 Content rules" }[k];
            return <li key={k}>{label} — {docs[k] ? "✅ written" : "⏳ pending…"}</li>;
          })}
        </ul>
      </div>
    </div>
  );
}

function InfoCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="card" style={{ margin: 0 }}>
      <div style={{ fontSize: 28 }}>{icon}</div>
      <p className="note" style={{ margin: "4px 0 0" }}>{label}</p>
      <h2 style={{ margin: 0, fontSize: 22 }}>{value}</h2>
    </div>
  );
}

function PostsGrid({ posts }: { posts: Post[] }) {
  if (posts.length === 0) {
    return <div className="card"><p className="note">No posts planned yet. The Strategist agent will populate this once brand docs are ready.</p></div>;
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 14 }}>
      {posts.map((p, i) => {
        const st = STATUS_STYLE[p.status] || STATUS_STYLE.planned;
        return (
          <div key={p.id} className="card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
              <span style={{ fontSize: 11, padding: "3px 8px", borderRadius: 20, background: st.bg, color: st.fg, fontWeight: 600 }}>
                {st.label}
              </span>
              <span className="note" style={{ fontSize: 11 }}>{p.post_type} · {p.duration_seconds}s</span>
            </div>
            <h4 style={{ margin: "10px 0 6px" }}>{p.title}</h4>
            {p.hook && <p style={{ fontSize: 15, fontWeight: 600, color: "var(--approved)", margin: "6px 0" }}>"{p.hook}"</p>}
            {p.script && <p className="note" style={{ fontSize: 12, maxHeight: 60, overflow: "hidden", margin: "6px 0" }}>{p.script.slice(0, 160)}{p.script.length > 160 ? "…" : ""}</p>}
            {p.caption && <p style={{ fontSize: 12, color: "var(--dim)", marginTop: 6 }}>{p.caption.slice(0, 140)}{p.caption.length>140?"…":""}</p>}
            {p.hashtags?.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                {p.hashtags.slice(0,8).map((h: string) => (
                  <span key={h} style={{ fontSize: 11, padding: "2px 7px", borderRadius: 10, background: "var(--bg)", border: "1px solid var(--line)", color: "var(--scheduled)" }}>#{h}</span>
                ))}
              </div>
            )}
            <p className="note" style={{ fontSize: 10, marginTop: 8 }}>#{i+1} · pillar: {p.metadata?.pillar || p.post_type}</p>
          </div>
        );
      })}
    </div>
  );
}
