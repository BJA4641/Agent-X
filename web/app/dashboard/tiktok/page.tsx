export const dynamic = "force-dynamic";
import PlatformHub from "@/components/PlatformHub";

export default function TikTokPage() {
  return (
    <PlatformHub platformKey="tiktok" courseId="tiktok"
      title="TikTok"
      blurb="Your third distribution surface. Same videos the Studio already makes — posted in-app, on purpose.">
      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">Why manual (for now)</p>
        <p style={{ fontSize: 14, lineHeight: 1.7 }}>TikTok rewards in-app uploads and
        trending sounds, and its API posting is gated for new apps. So TikTok runs as a
        5-minute daily ritual using the Studio&apos;s cross-post pack — you lose nothing and
        gain the algorithm&apos;s preference for native posts.</p>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">The 5-minute daily workflow</p>
        <ol style={{ fontSize: 14, lineHeight: 2, paddingLeft: 18 }}>
          <li>Open <b>Studio</b> → today&apos;s approved clip → <b>Download video ↓</b> to your phone.</li>
          <li>Tap <b>Copy TikTok</b> — caption + hashtags land on your clipboard.</li>
          <li>In TikTok: upload, paste the caption, add a trending sound at ~10% volume under the voiceover.</li>
          <li>Post 6–10pm your audience&apos;s time. Reply to the first comments fast.</li>
        </ol>
      </div>
      <div className="honest" style={{ marginTop: 16 }}>
        <b>Money honesty:</b> Creator Rewards pays only for 60s+ videos, needs 10k
        followers + 100k views/30d, and covers about ten countries (not the Middle East
        or Türkiye yet). Treat TikTok as a growth engine feeding your link-in-bio, email
        list and product — never fake eligibility with a VPN; that is a ban.
      </div>
    </PlatformHub>
  );
}
