export const dynamic = "force-dynamic";

export default function TikTok() {
  return (
    <>
      <h2>TikTok</h2>
      <p className="lead">Your third distribution surface. Same videos the Studio already makes — posted in-app, on purpose.</p>

      <div className="card" style={{ marginTop: 24 }}>
        <p className="eyebrow">Why manual (for now)</p>
        <p style={{ fontSize: 14, lineHeight: 1.7 }}>TikTok rewards in-app uploads and trending sounds, and its API posting is gated for new apps. So TikTok runs as a 5-minute daily ritual using the Studio&apos;s cross-post pack — you lose nothing and gain the algorithm&apos;s preference for native posts.</p>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">The 5-minute daily workflow</p>
        <ol style={{ fontSize: 14, lineHeight: 2, paddingLeft: 18 }}>
          <li>Open <b>Studio</b> → today&apos;s approved clip → <b>Download video ↓</b> to your phone.</li>
          <li>Tap <b>Copy TikTok</b> — caption + hashtags land on your clipboard.</li>
          <li>In TikTok: upload the video, paste the caption, then <b>add a trending sound at low volume (~10%)</b> under the voiceover — sound choice is TikTok&apos;s biggest free reach lever.</li>
          <li>Post between 6–10pm your audience&apos;s time. Reply to the first comments fast.</li>
        </ol>
      </div>

      <div className="honest" style={{ marginTop: 16 }}>
        <b>Money honesty:</b> TikTok&apos;s Creator Rewards Program pays only for videos over 60s, requires 10k followers + 100k views/30d, and is available in about ten countries (US, UK, DE, FR, JP, KR, BR, MX — not the Middle East or Türkiye yet). Do not build the business on TikTok payouts: here it is a growth engine that feeds your link-in-bio, your email list, and your product — the layers that pay from day one. Never use a VPN to fake eligibility; that is a ban.
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">Growth notes that matter on TikTok specifically</p>
        <ul style={{ fontSize: 14, lineHeight: 2, paddingLeft: 18 }}>
          <li>Volume is tolerated: 1–3 posts/day is normal here — your Studio can feed all of them.</li>
          <li>First 2 seconds decide everything: the Studio&apos;s hook A/B picker is your friend — pick the sharper hook for TikTok.</li>
          <li>Watch your retention graph in TikTok analytics; kill formats that dip before 3s.</li>
          <li>Put your link-in-bio the moment TikTok allows it (1k followers) — until then, name-drop your IG handle in the caption.</li>
        </ul>
      </div>
    </>
  );
}
