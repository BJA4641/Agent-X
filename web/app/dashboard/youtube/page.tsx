export const dynamic = "force-dynamic";
import PlatformHub from "@/components/PlatformHub";

export default function YouTubePage() {
  return (
    <PlatformHub platformKey="youtube" courseId="youtube"
      title="YouTube"
      blurb="Shorts for reach, long-form for revenue. The only platform where the content itself pays (YPP) instead of only what it links to.">
      <div className="honest" style={{ marginTop: 16 }}>
        <b>Publishing honesty:</b> YouTube upload via API needs an OAuth build
        (Google Cloud project + consent screen) that isn't wired yet — flagged in the
        roadmap. Until then: download from Studio, upload natively, paste the
        SEO title + description the pipeline already writes for every post.
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">Money honesty — YPP requirements</p>
        <p style={{ fontSize: 14, lineHeight: 1.7 }}>
          Partner Program needs 1,000 subscribers plus either 4,000 public watch
          hours (12 months) or 10M Shorts views (90 days). Shorts RPM is small;
          the real YouTube money is long-form ads + affiliate links in descriptions.
          Build Shorts for subscribers, then convert with long-form. No shortcuts,
          no bought subs — that kills monetization review.
        </p>
      </div>
    </PlatformHub>
  );
}
