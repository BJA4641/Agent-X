import Header from "@/components/Header";
import Waitlist from "@/components/Waitlist";
import { TRACKS } from "@/lib/tracks";

const MONEY_PATHS = [
  { emoji: "🎯", title: "Affiliate from view one", body: "Link tools you actually feature. No follower minimum. Disclosure built into every step." },
  { emoji: "📺", title: "YouTube ad revenue (long-form)", body: "The only 'paid per view' model that scales. Shorts feed the long-form ladder that hits YPP." },
  { emoji: "🛍️", title: "Your own ecommerce brand", body: "Proven product → your brand → your store. Rebrand, don't resell, to survive the algo and the margins." },
  { emoji: "🧲", title: "Comment → DM → email → product", body: "A $17–47 digital product sold to the list you build. This is the highest-margin lever on the whole map." },
  { emoji: "💰", title: "Creator bonuses when eligible", body: "TikTok Rewards, Instagram bonuses — optional top-up, never the plan A. We tell you exactly when they unlock." },
  { emoji: "🤝", title: "Brand deals later", body: "Once you have a real niche audience, inbound pays per post. Not a day-one promise." },
];

export default function Landing() {
  return (
    <>
      <Header />
      <main>
        <div className="wrap hero">
          <p className="eyebrow">Agent-X · autonomous AI agents that build you real income streams</p>
          <h1>From zero to your first online money stream — step by step, with AI agents doing the heavy work.</h1>
          <p className="sub">
            Pick a money path. Agents research, write scripts, draft Reels/Shorts/TikToks and a rebrandable store.
            You approve. Nothing gets published or launched until you say so. Every step is a verified checkbox,
            every method is the version that actually pays in 2026.
          </p>

          <div className="timeline" role="img" aria-label="Agent pipeline: strategy → draft → you approve → scheduled → published → paid">
            <div className="ruler"><span>agents work</span><span>you review</span><span>publish</span><span>earn</span></div>
            <div className="clips">
              <div className="clip idea">strategy<small>picks proven angles</small></div>
              <div className="clip draft">content<small>script + voice + video</small></div>
              <div className="clip approved">you approve<small>green light = yours</small></div>
              <div className="clip scheduled">scheduled<small>multi-platform slots</small></div>
              <div className="clip published">published<small>tracked to income</small></div>
            </div>
            <p className="legend">Five agent stations, one human editor. The <b>green step is you</b> — agents never skip it.</p>
          </div>
        </div>

        <section id="how">
          <div className="wrap">
            <h2>How Agent-X works</h2>
            <p className="lead">A team of AI agents running 24/7 on your accounts. You are the CEO, not the intern.</p>
            <div className="grid3">
              <div className="card"><h3>🧠 Strategy agent</h3><p>Reads trends, competitor outliers, your own analytics, and queues angles that have already proven they get attention — original scripts, never reposts.</p></div>
              <div className="card"><h3>🎬 Content studio</h3><p>Scripts, AI voiceovers, captioned vertical video for Reels/Shorts/TikTok, and long-form YouTube outlines — delivered to your approval queue.</p></div>
              <div className="card"><h3>🛒 Brand &amp; commerce</h3><p>Researches winning products, writes your brand bible, drafts a Shopify-style store, and generates creatives for your rebranded offer.</p></div>
              <div className="card"><h3>✅ QA agent</h3><p>Flags policy risks, generic spam, broken hooks, and missing disclosures before anything ships. You only see clean output.</p></div>
              <div className="card"><h3>💸 Monetization agent</h3><p>Tracks affiliate links, bonus eligibility, product funnel steps and wallet spend, so you know what is actually earning.</p></div>
              <div className="card"><h3>👀 You stay in control</h3><p>One-click approve / edit / reject. Slack-style feed shows every agent's work. Connect your own channels — we never hold your logins.</p></div>
            </div>
            <div className="honest">
              <b>Honest economics up front:</b> no one gets paid for spamming reposts anymore. Instagram/YouTube/TikTok
              all demonetize straight copies. Agent-X clones the ANGLE — same hook structure, original content —
              which is the only safe long-term approach. No income promises: results depend on your consistency,
              your niche, and your edits. We give you the correct process.
            </div>
          </div>
        </section>

        <section id="money">
          <div className="wrap">
            <h2>Six ways you actually get paid</h2>
            <p className="lead">Verified against 2026 platform rules and affiliate programs. Each one has its own course track with check-off steps.</p>
            <div className="grid3">
              {MONEY_PATHS.map((p) => (
                <div className="card" key={p.title}>
                  <h3><span style={{ fontSize: 28, marginRight: 8 }}>{p.emoji}</span>{p.title}</h3>
                  <p>{p.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="tracks">
          <div className="wrap">
            <h2>Start a track — each one is a step-by-step path to a paid outcome</h2>
            <p className="lead">Every step is a checkbox with proof (screenshot / link / text). You cannot skip to "posting" before the foundations that actually make money are in place.</p>
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
            <h2>Built in public, from Istanbul</h2>
            <p className="lead">
              We run our own pages and stores on this exact system. The waitlist gets the live case study —
              real agent feed, real numbers, wins and misses — before anything is sold. Public build log lives
              at <a href="/proof" style={{ color: "var(--scheduled)" }}>/proof</a>.
            </p>
            <Waitlist />
            <p className="note">One email when the next money-path ships. No sequences, no spam.</p>
          </div>
        </section>
      </main>
      <footer className="site"><div className="wrap">© {new Date().getFullYear()} Agent-X · You own your accounts, your brand, and your revenue — we never hold your logins.</div></footer>
    </>
  );
}
