export const dynamic = "force-dynamic";
import PlatformHub from "@/components/PlatformHub";

export default function InstagramPage() {
  return (
    <PlatformHub platformKey="instagram" courseId="instagram"
      title="Instagram"
      blurb="Reels from the Studio, posted daily. Your primary discovery surface and the front door to affiliate + product income.">
      <div className="honest" style={{ marginTop: 16 }}>
        <b>Publishing honesty:</b> automated posting to Instagram requires the Graph
        API with an approved app and a Business/Creator account — until that OAuth flow
        ships, posting is the same 5-minute manual ritual as TikTok: download the
        approved clip from Studio, copy the caption pack, post natively. The pipeline
        still plans, writes, grades and renders everything automatically.
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <p className="eyebrow">What actually grows Instagram in 2026</p>
        <ul style={{ fontSize: 14, lineHeight: 2, paddingLeft: 18 }}>
          <li>Reels with a hook inside 1.5s — the Studio grader already enforces this.</li>
          <li>3–5 quality posts per week beats daily filler; saves + shares outrank likes.</li>
          <li>Link-in-bio is your money page: one affiliate link or product, not a link farm.</li>
          <li>Reply to every early comment — first-hour engagement decides distribution.</li>
        </ul>
      </div>
    </PlatformHub>
  );
}
