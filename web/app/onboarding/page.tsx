"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const NICHES: { slug: string; name: string; emoji: string; desc: string }[] = [
  { slug: "ai_tools", name: "AI tools", emoji: "🤖", desc: "Tutorials, walkthroughs, productivity hacks." },
  { slug: "fitness", name: "Fitness", emoji: "💪", desc: "Workouts, form, nutrition." },
  { slug: "finance", name: "Finance", emoji: "💰", desc: "Investing, side hustles, money tips." },
  { slug: "cooking", name: "Cooking", emoji: "🍳", desc: "Quick recipes, meal prep, hacks." },
  { slug: "skincare", name: "Skincare", emoji: "🧴", desc: "Routines, product reviews, glow tips." },
  { slug: "gaming", name: "Gaming", emoji: "🎮", desc: "Clips, tips, tier lists." },
  { slug: "real_estate", name: "Real estate", emoji: "🏠", desc: "Investing, agent tips, tours." },
  { slug: "saas", name: "SaaS / B2B", emoji: "📈", desc: "Growth, founder stories, marketing." },
  { slug: "coaching", name: "Coaching", emoji: "🧠", desc: "Mindset, discipline, self-improvement." },
  { slug: "travel", name: "Travel", emoji: "✈️", desc: "Hacks, itineraries, hidden gems." },
  { slug: "fashion", name: "Fashion", emoji: "👗", desc: "Outfits, styling, trends." },
  { slug: "parenting", name: "Parenting", emoji: "👶", desc: "Hacks, relatable moments, advice." },
  { slug: "crypto", name: "Crypto", emoji: "₿", desc: "News, alpha, risk-managed plays." },
  { slug: "music", name: "Music", emoji: "🎵", desc: "Production, beats, mixing." },
  { slug: "pets", name: "Pets", emoji: "🐾", desc: "Wholesome clips, training tips." },
  { slug: "diy", name: "DIY", emoji: "🔨", desc: "Projects, home hacks, builds." },
  { slug: "cars", name: "Cars", emoji: "🚗", desc: "Mods, reviews, maintenance." },
  { slug: "education", name: "Education", emoji: "📚", desc: "Study tips, exam prep, learning." },
  { slug: "productivity", name: "Productivity", emoji: "⚡", desc: "Systems, Notion, life optimization." },
  { slug: "mental_health", name: "Mental health", emoji: "💚", desc: "Coping, therapy, self-care." },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(null);
  const [pageName, setPageName] = useState("");
  const [platforms, setPlatforms] = useState<Record<string, boolean>>({
    instagram: true, youtube: false, tiktok: false, x: false,
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    fetch("/api/me/profile").then(r => r.json()).then((j) => {
      if (j.onboarded) router.push("/dashboard");
      if (j.niche) setSelected(j.niche);
      if (j.pageName) setPageName(j.pageName);
    }).catch(() => {});
  }, [router]);

  async function save() {
    if (!selected) return alert("Pick your niche first.");
    setBusy(true);
    const chosenPlatforms = Object.entries(platforms).filter(([, v]) => v).map(([k]) => k);
    const r = await fetch("/api/me/profile", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ niche: selected, page_name: pageName, platforms: chosenPlatforms, onboarded: true }),
    });
    setBusy(false);
    if (r.ok) { setDone(true); setTimeout(() => router.push("/dashboard"), 800); }
    else alert("Save failed — refresh and try again.");
  }

  return (
    <div className="wrap" style={{ paddingTop: 48, maxWidth: 900 }}>
      <h1>Pick your niche</h1>
      <p className="lead">Choose one niche to start. Your Studio, training clips, and trend feed are tailored to it. You can add more later.</p>

      <div className="grid3" style={{ marginTop: 24 }}>
        {NICHES.map((n) => (
          <div key={n.slug}
               onClick={() => setSelected(n.slug)}
               className="card"
               style={{ cursor: "pointer", borderColor: selected === n.slug ? "var(--approved)" : undefined }}>
            <div style={{ fontSize: 30 }}>{n.emoji}</div>
            <h3 style={{ margin: "6px 0" }}>{n.name}</h3>
            <p className="note" style={{ fontSize: 13 }}>{n.desc}</p>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 40 }}>Your page</h2>
      <div style={{ display: "grid", gap: 10, maxWidth: 480, marginTop: 10 }}>
        <input className="mono" placeholder="Page/brand name (e.g. Tool of the Future)"
               value={pageName} onChange={(e) => setPageName(e.target.value)}
               style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" }} />
        <div>
          <p className="note" style={{ marginBottom: 6 }}>Platforms you'll build first:</p>
          {Object.keys(platforms).map((p) => (
            <label key={p} style={{ marginRight: 16 }}>
              <input type="checkbox" checked={platforms[p]}
                     onChange={(e) => setPlatforms({ ...platforms, [p]: e.target.checked })} /> {p}
            </label>
          ))}
        </div>
        <button onClick={save} disabled={busy || !selected} style={{ marginTop: 10 }}>
          {busy ? "Saving…" : done ? "✓ Entering studio" : "Start building →"}
        </button>
      </div>
    </div>
  );
}
