import Header from "@/components/Header";
import Waitlist from "@/components/Waitlist";
import { TRACKS } from "@/lib/tracks";

export default function Landing() {
  return (
    <>
      <Header />
      <main>
        <div className="wrap hero">
          <p className="eyebrow">A production line for one-person media</p>
          <h1>Your content page, run like a studio.</h1>
          <p className="sub">
            BuildAlong plans topics, drafts faceless vertical videos, and queues them on a board.
            Nothing publishes until you press approve — you stay the editor, the machine does the grind.
          </p>

          {/* signature: the real board state machine as an editor timeline */}
          <div className="timeline" role="img" aria-label="Content pipeline: idea, draft, your approval, scheduled, published">
            <div className="ruler"><span>mon</span><span>tue</span><span>wed</span><span>thu</span><span>fri</span></div>
            <div className="clips">
              <div className="clip idea">idea<small>strategy queues it</small></div>
              <div className="clip draft">drafted<small>script + voice + video</small></div>
              <div className="clip approved">approved<small>one click — yours</small></div>
              <div className="clip scheduled">scheduled<small>next open slot</small></div>
              <div className="clip published">published<small>receipts + metrics</small></div>
            </div>
            <p className="legend">Every video moves left to right. The <b>green step is you</b> — the system never skips it.</p>
          </div>
        </div>

        <section id="how">
          <div className="wrap">
            <h2>How it works</h2>
            <p className="lead">One loop, five states. The same board you see above is the actual data model.</p>
            <div className="grid3">
              <div className="card"><h3>Strategy reads the numbers</h3><p>Winners and losers from last week decide next week's topics. No performance data yet? It starts from a proven angle and learns.</p></div>
              <div className="card"><h3>The Studio drafts</h3><p>Script, narration, per-beat visuals, and a 1080×1920 render with motion — a post-ready Reel per topic.</p></div>
              <div className="card"><h3>You approve, it ships</h3><p>Approve or reject from the board. Approved clips get slots and publish with receipts — never twice, capped by a daily budget you set.</p></div>
            </div>
            <div className="honest">
              <b>What this is not:</b> a get-rich machine. Platforms throttle soulless automation, and we build for the opposite —
              your judgment on every clip, your accounts, your audience. No income promises here or anywhere.
            </div>
          </div>
        </section>

        <section id="tracks">
          <div className="wrap">
            <h2>Start with one track</h2>
            <p className="lead">Instagram opens first. The other tracks unlock as the system earns it — same engine, new surfaces.</p>
            <div className="grid3">
              {TRACKS.map((t) => (
                <div className="card" key={t.id}>
                  <p style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                    <span className={t.state === "live" ? "tag live" : "tag"}>{t.state === "live" ? "open" : "coming next"}</span>
                    <span className="mono" style={{ fontSize: 13, color: "var(--dim)" }}>{t.price === 0 ? "free" : `$${t.price}`}</span>
                  </p>
                  <h3>{t.name}</h3>
                  <p>{t.blurb}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="waitlist">
          <div className="wrap">
            <h2>Built in public</h2>
            <p className="lead">
              We run our own pages on this exact system. The waitlist gets the live case study — real board,
              real numbers, wins and misses — before anything is sold. It will live at <a href="/proof" style={{ color: "var(--scheduled)" }}>/proof</a>.
            </p>
            <Waitlist />
            <p className="note">One email when the case study ships. No sequences, no spam.</p>
          </div>
        </section>
      </main>
      <footer className="site"><div className="wrap">© {new Date().getFullYear()} BuildAlong · You own your accounts; we never hold your logins.</div></footer>
    </>
  );
}
