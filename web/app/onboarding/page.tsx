"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

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

const STARTING_PATH = [
  { id: "social", label: "Social media (Reels/Shorts/TikToks)" },
  { id: "ecom", label: "Ecommerce / own brand store" },
  { id: "affiliate", label: "Affiliate marketing only" },
  { id: "multi", label: "I want everything (content + store + affiliate)" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [path, setPath] = useState<string>("social");
  const [selected, setSelected] = useState<string | null>(null);
  const [pageName, setPageName] = useState("");
  const [platforms, setPlatforms] = useState<Record<string, boolean>>({
    instagram: true, youtube: false, tiktok: false, x: false,
  });
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/me/profile").then(r => r.json()).then((j) => {
      if (j.onboarded) router.push("/dashboard");
      if (j.niche) setSelected(j.niche);
      if (j.page_name) setPageName(j.page_name);
      if (j.platforms && Array.isArray(j.platforms)) {
        const p: Record<string, boolean> = { instagram: false, youtube: false, tiktok: false, x: false };
        j.platforms.forEach((k: string) => { p[k] = true; });
        setPlatforms(p);
      }
    }).catch(() => {});
  }, [router]);

  async function save() {
    setError(null);
    setBusy(true);
    try {
      const chosenPlatforms = Object.entries(platforms).filter(([, v]) => v).map(([k]) => k);
      const r = await fetch("/api/me/profile", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          niche: path === "social" || path === "multi" ? selected : null,
          page_name: pageName || null,
          platforms: chosenPlatforms,
          starting_path: path,
          onboarded: true,
        }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.error || "Save failed");
      }
      setDone(true);
      setTimeout(() => router.push("/dashboard"), 800);
    } catch (e: any) {
      setError(e.message || "Save failed — refresh and try again.");
    } finally {
      setBusy(false);
    }
  }

  const showNichePicker = path === "social" || path === "multi";
  const canSave = !showNichePicker || !!selected;

  return (
    <div className="wrap" style={{ paddingTop: 32, paddingBottom: 64, maxWidth: 960 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <p className="eyebrow">Workspace setup</p>
          <h1 style={{ margin: "4px 0" }}>Tell Agent-X what you want to build first</h1>
          <p className="lead" style={{ maxWidth: 640 }}>
            This tunes the AI agents to YOUR goal — content, ecommerce, or both. You can change it later.
            Skip if you just want to explore.
          </p>
        </div>
        <Link href="/dashboard" className="tag" style={{ textDecoration: "none", fontSize: 14 }}>Skip → dashboard</Link>
      </div>

      <h2 style={{ marginTop: 36 }}>1. What's your first money path?</h2>
      <div style={{ display: "grid", gap: 10, maxWidth: 700, marginTop: 10 }}>
        {STARTING_PATH.map((p) => (
          <label key={p.id} className="card" style={{
            cursor: "pointer", display: "flex", alignItems: "center", gap: 12, padding: "12px 16px",
            borderColor: path === p.id ? "var(--approved)" : "var(--line)",
            margin: 0,
          }}>
            <input type="radio" name="path" checked={path === p.id} onChange={() => setPath(p.id)} />
            <span style={{ fontWeight: 500 }}>{p.label}</span>
          </label>
        ))}
      </div>

      {showNichePicker && (
        <>
          <h2 style={{ marginTop: 36 }}>2. Pick your content niche</h2>
          <p className="note">Choose one niche to start — the agents tailor scripts, trend feeds, and hooks to it.</p>
          <div className="grid3" style={{ marginTop: 16 }}>
            {NICHES.map((n) => (
              <div key={n.slug}
                   onClick={() => setSelected(n.slug)}
                   className="card"
                   style={{ cursor: "pointer", borderColor: selected === n.slug ? "var(--approved)" : undefined, margin: 0 }}>
                <div style={{ fontSize: 28 }}>{n.emoji}</div>
                <h4 style={{ margin: "6px 0 4px" }}>{n.name}</h4>
                <p className="note" style={{ fontSize: 13, margin: 0 }}>{n.desc}</p>
              </div>
            ))}
          </div>

          <h2 style={{ marginTop: 40 }}>3. Your page / brand</h2>
          <div style={{ display: "grid", gap: 12, maxWidth: 520, marginTop: 10 }}>
            <input className="mono" placeholder="Page or brand name (e.g. Tool of the Future)"
                   value={pageName} onChange={(e) => setPageName(e.target.value)}
                   style={{ background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 8, padding: "10px 12px", color: "inherit" }} />
            <div>
              <p className="note" style={{ marginBottom: 6 }}>Platforms you'll post to first:</p>
              {Object.keys(platforms).map((p) => (
                <label key={p} style={{ marginRight: 16 }}>
                  <input type="checkbox" checked={platforms[p]}
                         onChange={(e) => setPlatforms({ ...platforms, [p]: e.target.checked })} /> {p}
                </label>
              ))}
            </div>
          </div>
        </>
      )}

      {path === "ecom" && (
        <div style={{ marginTop: 24 }} className="honest">
          You're starting with ecommerce. You'll land on the dashboard — open the
          <b> Store rebranding</b> track to begin product research. The content agents
          stay available for ad creatives later.
        </div>
      )}
      {path === "affiliate" && (
        <div style={{ marginTop: 24 }} className="honest">
          You're starting with affiliate only. Open the <b>Affiliate links</b> track
          to pick programs, set up a link-in-bio, and learn the disclosure rules.
        </div>
      )}

      {error && (
        <div style={{ marginTop: 20, padding: 12, borderRadius: 8, border: "1px solid var(--failed)", color: "var(--failed)" }}>
          {error}
        </div>
      )}

      <div style={{ marginTop: 28, display: "flex", gap: 12, alignItems: "center" }}>
        <button onClick={save} disabled={busy || !canSave}>
          {busy ? "Saving…" : done ? "✓ Heading to dashboard" : "Start building →"}
        </button>
        <Link href="/dashboard" style={{ color: "var(--dim)" }}>Skip for now</Link>
      </div>
    </div>
  );
}
