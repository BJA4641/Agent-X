/* arena.ts — arena.ai (LMArena) leaderboard reader.
   arena.ai has no official API, so we read a free community mirror that snapshots
   all leaderboards daily (github: oolong-tea-2026/arena-ai-leaderboards). If the
   mirror is down we serve the baked snapshot below so the page never breaks. */

export type ArenaModel = { rank: number; model: string; vendor: string; score: number; votes: number };
export type ArenaBoard = { slug: string; title: string; factory: string; models: ArenaModel[] };

const MIRROR = "https://api.wulong.dev/arena-ai-leaderboards/v1/leaderboard?name=";

export const BOARDS: { slug: string; title: string; factory: string }[] = [
  { slug: "text", title: "Text · scripts, captions, strategy", factory: "Wired ✓ — pick any engine in Settings; the custom-model box (via OpenRouter) reaches most of this board." },
  { slug: "text-to-image", title: "Text → Image · your video frames", factory: "Wired ✓ — Gemini image gen runs on your existing key. GPT-Image needs an OPENAI_API_KEY." },
  { slug: "image-edit", title: "Image Edit · the annotation editor", factory: "Ready to wire — Gemini image editing uses the key you already have. Powers the circle-and-describe editor in v1.4." },
  { slug: "text-to-video", title: "Text → Video", factory: "Roadmap — one fal.ai key unlocks Seedance, Kling, Wan and Veo through a single API." },
  { slug: "image-to-video", title: "Image → Video · animate your frames", factory: "Roadmap — same fal.ai door; this is how static slideshows become full motion." },
  { slug: "video-edit", title: "Video Edit", factory: "Roadmap — youngest category; via fal.ai / Replicate when quality settles." },
];

const FALLBACK: Record<string, ArenaModel[]> = {
  "text": [
    { rank: 1, model: "claude-fable-5", vendor: "Anthropic", score: 1507, votes: 8819 },
    { rank: 2, model: "claude-opus-4-6-thinking", vendor: "Anthropic", score: 1504, votes: 61003 },
    { rank: 3, model: "claude-opus-4-7-thinking", vendor: "Anthropic", score: 1503, votes: 48292 },
    { rank: 4, model: "claude-opus-4-6", vendor: "Anthropic", score: 1498, votes: 64747 },
    { rank: 5, model: "claude-opus-4-7", vendor: "Anthropic", score: 1494, votes: 49467 },
    { rank: 6, model: "muse-spark-1.1", vendor: "Meta", score: 1493, votes: 5729 },
  ],
  "text-to-image": [
    { rank: 1, model: "gpt-image-2 (medium)", vendor: "OpenAI", score: 1385, votes: 60382 },
    { rank: 2, model: "reve-2.1", vendor: "Reve", score: 1302, votes: 2432 },
    { rank: 3, model: "muse-image", vendor: "Meta", score: 1280, votes: 8384 },
    { rank: 4, model: "reve-2.0", vendor: "Reve", score: 1271, votes: 13675 },
    { rank: 5, model: "gemini-3.1-flash-image (nano-banana-2)", vendor: "Google", score: 1261, votes: 18502 },
    { rank: 6, model: "mai-image-2.5", vendor: "Microsoft AI", score: 1257, votes: 34416 },
  ],
  "image-edit": [
    { rank: 1, model: "gpt-image-2 (medium)", vendor: "OpenAI", score: 1465, votes: 145970 },
    { rank: 2, model: "muse-image", vendor: "Meta", score: 1402, votes: 16932 },
    { rank: 3, model: "mai-image-2.5", vendor: "Microsoft AI", score: 1401, votes: 100526 },
    { rank: 4, model: "seedream-5.0-pro", vendor: "Bytedance", score: 1393, votes: 4299 },
    { rank: 5, model: "chatgpt-image-latest-high-fidelity", vendor: "OpenAI", score: 1389, votes: 457021 },
    { rank: 6, model: "grok-imagine-image-quality", vendor: "xAI", score: 1389, votes: 34756 },
  ],
  "text-to-video": [
    { rank: 1, model: "gemini-omni-flash", vendor: "Google", score: 1527, votes: 5449 },
    { rank: 2, model: "dreamina-seedance-2.0-720p", vendor: "Bytedance", score: 1482, votes: 41953 },
    { rank: 3, model: "muse-video", vendor: "Meta", score: 1459, votes: 2152 },
    { rank: 4, model: "happyhorse-1.0", vendor: "Alibaba-ATH", score: 1430, votes: 21985 },
    { rank: 5, model: "sora-2-pro", vendor: "OpenAI", score: 1366, votes: 39773 },
    { rank: 6, model: "veo-3.1-audio-1080p", vendor: "Google", score: 1364, votes: 23200 },
  ],
  "image-to-video": [
    { rank: 1, model: "dreamina-seedance-2.0-720p", vendor: "Bytedance", score: 1474, votes: 81746 },
    { rank: 2, model: "gemini-omni-flash", vendor: "Google", score: 1469, votes: 5373 },
    { rank: 3, model: "grok-imagine-video-1.5-preview", vendor: "xAI", score: 1466, votes: 44400 },
    { rank: 4, model: "happyhorse-1.0", vendor: "Alibaba-ATH", score: 1444, votes: 61051 },
    { rank: 5, model: "wan2.7-i2v", vendor: "Alibaba", score: 1434, votes: 14113 },
    { rank: 6, model: "grok-imagine-video-720p", vendor: "xAI", score: 1422, votes: 462748 },
  ],
  "video-edit": [
    { rank: 1, model: "dreamina-seedance-2.0-720p", vendor: "Bytedance", score: 1377, votes: 3010 },
    { rank: 2, model: "gemini-omni-flash", vendor: "Google", score: 1347, votes: 998 },
    { rank: 3, model: "happyhorse-1.0", vendor: "Alibaba-ATH", score: 1308, votes: 2681 },
    { rank: 4, model: "grok-imagine-video", vendor: "xAI", score: 1264, votes: 11736 },
    { rank: 5, model: "kling-o3-pro", vendor: "KlingAI", score: 1251, votes: 6165 },
    { rank: 6, model: "kling-o1-pro", vendor: "KlingAI", score: 1203, votes: 8322 },
  ],
};

export async function fetchBoards(): Promise<{ boards: ArenaBoard[]; live: boolean }> {
  let live = true;
  const boards = await Promise.all(BOARDS.map(async (b) => {
    try {
      const r = await fetch(MIRROR + b.slug, { next: { revalidate: 86400 } });
      if (!r.ok) throw new Error();
      const j = await r.json();
      const models = (j.models || []).slice(0, 6).map((m: any) => ({
        rank: m.rank, model: m.model, vendor: m.vendor, score: m.score, votes: m.votes }));
      if (!models.length) throw new Error();
      return { ...b, models };
    } catch {
      live = false;
      return { ...b, models: FALLBACK[b.slug] };
    }
  }));
  return { boards, live };
}
