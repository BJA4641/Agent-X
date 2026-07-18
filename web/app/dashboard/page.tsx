import Link from "next/link";
import { TRACKS } from "@/lib/tracks";
import { supabaseServer } from "@/lib/supabase/server";

export default async function Dashboard() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  const { data: ents } = await sb.from("entitlements").select("module_id");
  const owned = new Set((ents || []).map((e) => e.module_id));
  return (
    <>
      <h2>Your tracks</h2>
      <p className="lead">Instagram is open for everyone. The others unlock when they open.</p>
      <div className="grid3">
        {TRACKS.map((t) => {
          const open = t.price === 0 || owned.has(t.id);
          return (
            <div className="card" key={t.id}>
              <p style={{ marginBottom: 10 }}><span className={t.state === "live" ? "tag live" : "tag"}>{t.state === "live" ? "open" : "coming next"}</span></p>
              <h3>{t.name}</h3>
              <p>{t.blurb}</p>
              <p style={{ marginTop: 14 }}>
                {open && t.state === "live"
                  ? <Link href={`/dashboard/${t.id}`} style={{ color: "var(--scheduled)" }}>Open track →</Link>
                  : <span className="note">{t.state === "soon" ? "Opens after the Instagram case study." : ""}</span>}
              </p>
            </div>
          );
        })}
      </div>
    </>
  );
}
