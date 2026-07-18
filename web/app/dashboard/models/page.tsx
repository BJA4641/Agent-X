import { fetchBoards } from "@/lib/arena";

export const revalidate = 86400;

export default async function ModelsPage() {
  const { boards, live } = await fetchBoards();
  return (
    <div>
      <h1>AI model leaderboard</h1>
      <p className="note" style={{ maxWidth: 640 }}>
        Live rankings from <a href="https://arena.ai" target="_blank" rel="noreferrer">arena.ai</a> (LMArena) —
        millions of blind human votes, updated daily. Each section tells you whether your factory can use
        that category today. Text engines switch instantly in <a href="/dashboard/settings">Settings</a>.
      </p>
      {!live && <p className="note" style={{ color: "var(--draft)" }}>Live feed unreachable — showing the last saved snapshot.</p>}

      {boards.map((b) => (
        <div key={b.slug} style={{ marginTop: 32 }}>
          <h2>{b.title}</h2>
          <p className="note" style={{ maxWidth: 640 }}>{b.factory}</p>
          <div className="card" style={{ marginTop: 10, padding: 0, overflow: "hidden" }}>
            {b.models.map((m) => (
              <div key={m.rank + m.model} style={{ display: "flex", gap: 14, alignItems: "baseline",
                   padding: "10px 16px", borderBottom: "1px solid var(--line)" }}>
                <span className="mono" style={{ width: 24, color: m.rank === 1 ? "var(--draft)" : "var(--dim)" }}>#{m.rank}</span>
                <span style={{ flex: 1, fontWeight: m.rank === 1 ? 600 : 400 }}>{m.model}</span>
                <span className="tag">{m.vendor}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--dim)" }}>ELO {m.score}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--dim)" }}>{m.votes.toLocaleString()} votes</span>
              </div>
            ))}
          </div>
        </div>
      ))}
      <p className="note" style={{ marginTop: 24, maxWidth: 640 }}>
        arena.ai is a ranking site, not a generation service — it has no API for creating content.
        Your factory reads its rankings here, then calls the winning models directly through their own doors
        (OpenRouter, Gemini, fal.ai) so you always generate with a top-rated engine.
      </p>
    </div>
  );
}
