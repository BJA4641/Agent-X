import Header from "@/components/Header";
import { supabaseAdmin } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;
const TENANT = process.env.TENANT_ID || "me";

type Row = { id: string; topic: string; status: string; payload: any; created_at: string };

async function load(): Promise<Row[] | null> {
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY) return null;
  try {
    const { data } = await supabaseAdmin().from("board_items")
      .select("id,topic,status,payload,created_at").eq("tenant_id", TENANT)
      .in("status", ["published", "reported"]).order("created_at", { ascending: false }).limit(60);
    return (data as Row[]) || [];
  } catch { return null; }
}

const views = (r: Row) => Object.values(r.payload?.metrics || {}).reduce((a: number, m: any) => a + (m?.views || 0), 0);

export default async function Proof() {
  const rows = await load();
  const posted = rows?.length || 0;
  const totalViews = (rows || []).reduce((a, r) => a + views(r), 0);
  const best = (rows || []).slice().sort((a, b) => views(b) - views(a))[0];

  return (
    <>
      <Header />
      <main>
        <div className="wrap hero" style={{ paddingBottom: 24 }}>
          <p className="eyebrow">The case study — live data, not screenshots</p>
          <h1>We run our own pages on this system.</h1>
          <p className="sub">
            This page reads straight from the production board — the same database the agents write to.
            Wins and misses both stay up. No numbers are typed by hand.
          </p>
        </div>

        <section>
          <div className="wrap">
            {rows === null || posted === 0 ? (
              <div className="honest">
                <b>Day 0.</b> The engine is built and tested; the first videos publish when our Instagram page goes live.
                From that day this page fills itself — every clip, every view count, automatically.
                Join the waitlist on the <a href="/#waitlist" style={{ color: "var(--scheduled)" }}>home page</a> to get the first report.
              </div>
            ) : (
              <>
                <div className="grid3">
                  <div className="card"><p className="eyebrow">Clips published</p><h2 className="mono" style={{ fontSize: 40 }}>{posted}</h2></div>
                  <div className="card"><p className="eyebrow">Total views</p><h2 className="mono" style={{ fontSize: 40 }}>{totalViews.toLocaleString()}</h2></div>
                  <div className="card"><p className="eyebrow">Best clip</p><h3 style={{ marginTop: 8 }}>{best?.topic}</h3><p className="note">{views(best!).toLocaleString()} views</p></div>
                </div>
                <div className="steps" style={{ marginTop: 28 }}>
                  {rows!.map((r) => (
                    <div className="step" key={r.id} style={{ justifyContent: "space-between" }}>
                      <span><h4>{r.topic}</h4><p className="note">{new Date(r.created_at).toLocaleDateString()}</p></span>
                      <span className="mono" style={{ color: "var(--published)" }}>{views(r).toLocaleString()} views</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
      </main>
      <footer className="site"><div className="wrap">Data source: production board, refreshed on every page load.</div></footer>
    </>
  );
}
