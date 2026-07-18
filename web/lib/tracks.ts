export type Step = { key: string; title: string; detail: string; href?: string };
export type Track = {
  id: string; name: string; state: "live" | "soon";
  price: number; blurb: string; steps: Step[];
};

export const TRACKS: Track[] = [
  {
    id: "instagram", name: "Instagram page", state: "live", price: 0,
    blurb: "Stand up a faceless AI-education page and ship your first week of Reels with the Studio.",
    steps: [
      { key: "ig-1", title: "Create the account", detail: "Business/Creator account, real identity, one niche angle. You own it — we never hold your login.", href: "https://www.instagram.com" },
      { key: "ig-2", title: "Lock the angle", detail: "One sentence: who it's for + the daily promise. This becomes every caption's CTA." },
      { key: "ig-3", title: "Generate video #1 in the Studio", detail: "One topic in, one 1080×1920 Reel out. Watch it before you post — you are the editor." },
      { key: "ig-4", title: "Post manually, today", detail: "No API needed to start. The automation clock (Meta review) runs in parallel — the streak starts now." },
      { key: "ig-5", title: "Wire affiliate links", detail: "Link-in-bio with the tools you actually feature. Money from view one, no follower minimum." },
      { key: "ig-6", title: "Seven-day streak", detail: "One approved video a day. The board tracks it; the analytics decide week two." },
    ],
  },
  {
    id: "youtube", name: "YouTube Shorts", state: "soon", price: 200,
    blurb: "Same engine, second surface. Opens after your Instagram page has a real week of data.",
    steps: [
      { key: "yt-1", title: "Channel setup", detail: "Channel, branding, upload defaults." },
      { key: "yt-2", title: "Shorts pipeline", detail: "Reuse the Studio output; native captions and titles per platform." },
      { key: "yt-3", title: "Data API OAuth", detail: "Official auto-upload, your account, your tokens." },
    ],
  },
  {
    id: "store", name: "Ecommerce store", state: "live", price: 200,
    blurb: "Product research to first sale: find a proven product, rebrand it, build the store, launch with kill rules.",
    steps: [
      { key: "st-1", title: "8 modules, 17 verified steps", detail: "Research -> brand -> store -> creatives -> launch -> operations -> scale. Every step gated by proof." },
          ],
  },
];
export const trackById = (id: string) => TRACKS.find((t) => t.id === id);
