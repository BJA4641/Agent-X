import { supabaseServer } from "@/lib/supabase/server";
import { courseById } from "@/lib/courses";
import CourseView from "@/components/CourseView";
import { ReactNode } from "react";

/* v5.9.5 — PlatformHub: one live hub per social platform.
   Shows: (1) your real connected accounts on this platform,
          (2) the latest posts the pipeline produced for them,
          (3) the platform course + task tracker (restored — the old static
              pages had accidentally shadowed the [track] course view),
          (4) platform-specific guidance passed in as children.
   All data is read live from Supabase under the user's own RLS policies —
   nothing here is simulated. Empty states say so honestly. */

export default async function PlatformHub({
  platformKey, title, blurb, courseId, children,
}: {
  platformKey: string;        // substring matched against project_accounts.platforms
  title: string; blurb: string; courseId: string; children?: ReactNode;
}) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();

  // 1) accounts on this platform (RLS scopes to the signed-in user)
  const { data: accountsRaw } = await sb
    .from("project_accounts")
    .select("id,name,handle,niche,paused,posts_per_day,platforms")
    .order("created_at", { ascending: false });
  const accounts = (accountsRaw || []).filter((a) =>
    JSON.stringify(a.platforms || []).toLowerCase().includes(platformKey));

  // 2) latest pipeline posts for those accounts
  let posts: any[] = [];
  if (accounts.length) {
    const ids = accounts.map((a) => a.id);
    const { data } = await sb
      .from("account_posts")
      .select("id,account_id,title,status,scheduled_at,created_at")
      .in("account_id", ids)
      .order("created_at", { ascending: false })
      .limit(8);
    posts = data || [];
  }
  const byId: Record<string, any> = {};
  accounts.forEach((a) => { byId[a.id] = a; });

  // 3) course + progress (same source as the task tracker)
  const course = courseById(courseId);
  const { data: prog } = await sb.from("task_progress").select("task_key,done,proof");
  const progress: Record<string, any> = {};
  (prog || []).forEach((r) => { progress[r.task_key] = { done: r.done, proof: r.proof }; });

  return (
    <>
      <h2>{title}</h2>
      <p className="lead">{blurb}</p>

      <div className="card" style={{ marginTop: 24 }}>
        <p className="eyebrow">Your accounts on this platform</p>
        {accounts.length === 0 && (
          <p style={{ fontSize: 14 }}>
            No accounts run this platform yet. Add one in <b>Projects</b> and include
            “{platformKey}” in its platforms — the pipeline picks it up on the next tick.
          </p>
        )}
        {accounts.map((a) => (
          <div key={a.id} style={{ display: "flex", gap: 10, alignItems: "center",
            padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,.06)", fontSize: 14 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%",
              background: a.paused ? "#f59e0b" : "#22c55e" }} />
            <b>{a.name}</b><span style={{ opacity: .6 }}>@{a.handle}</span>
            <span style={{ opacity: .6 }}>· {a.niche}</span>
            <span style={{ marginLeft: "auto", opacity: .7 }}>
              {a.paused ? "paused" : `${a.posts_per_day}/day`}</span>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">Latest pipeline posts</p>
        {posts.length === 0 && (
          <p style={{ fontSize: 14 }}>
            Nothing produced for this platform yet — when the worker plans and drafts
            posts for your accounts they appear here with their real status.
          </p>
        )}
        {posts.map((p) => (
          <div key={p.id} style={{ display: "flex", gap: 10, padding: "7px 0",
            borderBottom: "1px solid rgba(255,255,255,.06)", fontSize: 13.5 }}>
            <span style={{ opacity: .6, minWidth: 92 }}>{byId[p.account_id]?.name || "—"}</span>
            <span style={{ flex: 1 }}>{p.title}</span>
            <span className="sidetag">{p.status}</span>
          </div>
        ))}
      </div>

      {children}

      {course && (
        <div style={{ marginTop: 24 }}>
          <p className="eyebrow">Course & task tracker</p>
          <CourseView course={course} initial={progress} locked={false} />
        </div>
      )}
      {!user && <p className="note" style={{ marginTop: 12 }}>Sign in to see your accounts and progress.</p>}
    </>
  );
}
