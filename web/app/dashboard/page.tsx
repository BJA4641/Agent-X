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
      <h2>Your income tracks</h2>
      <p className="lead">
        Each track is a verified path to real money. Start with ONE — don't open them all at once.
        Instagram Reels + affiliate is the fastest to first dollar; YouTube long-form is the highest lifetime value.
      </p>
      <div className="grid3">
        {TRACKS.map((t) => {
          const open = t.price === 0 || owned.has(t.id);
          return (
            <div className="card" key={t.id}>
              <p style={{ marginBottom: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className={t.state === "live" ? "tag live" : "tag"}>{t.state === "live" ? "open" : "coming next"}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--dim)" }}>{t.price === 0 ? "free" : `$${t.price}`}</span>
              </p>
              <h3>{t.name}</h3>
              <p style={{ color: "var(--approved)", fontSize: 13, marginBottom: 8 }}>💰 {t.incomeLayer}</p>
              <p>{t.blurb}</p>
              <p style={{ marginTop: 14 }}>
                {open && t.state === "live"
                  ? <Link href={`/dashboard/${t.id}`} style={{ color: "var(--scheduled)" }}>Open track →</Link>
                  : <span className="note">{t.state === "soon" ? "Module ships next — finish your first live track to unlock early access." : ""}</span>}
              </p>
            </div>
          );
        })}
      </div>
      <div className="honest" style={{ marginTop: 28 }}>
        <b>Rule #1 of the dashboard:</b> you only advance to the next track after finishing the current one's checkboxes.
        Spreading yourself across 5 platforms at day 5 is the #1 reason beginners earn zero. Pick. Ship. Earn. Then expand.
      </div>
    </>
  );
}
