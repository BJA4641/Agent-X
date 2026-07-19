import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import QueueTopic from "@/components/QueueTopic";

export const dynamic = "force-dynamic";

type TrendRow = {
  id: number; niche: string; platform: string; title: string; url: string;
  author: string | null; views: number; engagement: number; heat: number;
  published_at: string | null; scraped_at: string;
};

const PLATFORM_LABEL: Record<string, string> = {
  reddit: "Reddit", news: "News", hackernews: "Hacker News", youtube: "YouTube",
};

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}

function ago(iso: string | null): string {
  if (!iso) return "";
  const h = Math.max(0, (Date.now() - new Date(iso).getTime()) / 3.6e6);
  if (h < 1) return "just now";
  if (h < 24) return Math.round(h) + "h ago";
  return Math.round(h / 24) + "d ago";
}

// ---------- RSS fallback (used only until the scout's first pass lands) ----------
const FEEDS = [
  "https://news.google.com/rss/search?q=AI+tools+when:7d&hl=en-US&gl=US&ceid=US:en",
  "https://news.google.com/rss/search?q=ChatGPT+OR+Gemini+OR+Claude+feature+when:7d&hl=en-US&gl=US&ceid=US:en",
];

async function fetchText(url: string): Promise<string> {
  try {
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" }, next: { revalidate: 900 } });
    return r.ok ? await r.text() : "";
  } catch { return ""; }
}

function decodeHtml(s: string): string {
  if (!s) return s;
  return s
    .replace(/&amp;/g, "&").replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/&nbsp;/g, " ");
}

function headlines(xml: string): string[] {
  const out: string[] = [];
  const re = /<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?<\/title>/g;
  let m; let first = true;
  while ((m = re.exec(xml))) {
    if (first) { first = false; continue; }
    out.push(decodeHtml(m[1].replace(/\s*-\s*[^-]+$/, "").trim()));
  }
  return out;
}

export default async function Trends({ searchParams }: { searchParams?: { niche?: string } }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) redirect("/login");
  if (!isAdmin(user.email)) redirect("/dashboard");

  const nicheFilter = searchParams?.niche || "";
  const cutoff = new Date(Date.now() - 48 * 3.6e6).toISOString();

  let rows: TrendRow[] = [];
  let niches: string[] = [];
  try {
    let q = sb.from("trend_items").select("*").gte("scraped_at", cutoff)
      .order("heat", { ascending: false }).limit(60);
    if (nicheFilter) q = q.eq("niche", nicheFilter);
    const { data } = await q;
    rows = (data as TrendRow[]) || [];
    const { data: allN } = await sb.from("trend_items").select("niche").gte("scraped_at", cutoff).limit(500);
    niches = Array.from(new Set(((allN as { niche: string }[]) || []).map(r => r.niche))).sort();
  } catch { /* table missing -> fallback below */ }

  // fallback: same RSS pull as before, until the scout's first pass writes rows
  let fallback: string[] = [];
  if (rows.length === 0) {
    const xmls = await Promise.all(FEEDS.map(fetchText));
    const seen = new Set<string>();
    fallback = xmls.flatMap(headlines)
      .filter(t => t.length > 15 && !seen.has(t.toLowerCase()) && seen.add(t.toLowerCase()))
      .slice(0, 14);
  }

  return (
    <>
      <h2>Trend scout desk</h2>
      <p className="lead">
        The Scout agent sweeps Reddit, Google News, Hacker News{rows.some(r => r.platform === "youtube") ? ", YouTube" : ""} every
        ~30 minutes for each active niche and ranks what is genuinely hot right now
        (<b>heat</b> = engagement × freshness, 1–99). <b>Queue my version</b> drops the topic on the
        Studio board — the writer produces an <i>original</i> script on the proven pattern
        (topic + angle), never a repost. That is the version platforms reward and the one
        that survives YouTube&apos;s inauthentic-content rules; source metrics stay attached so
        you can compare your numbers against the original&apos;s.
      </p>

      {niches.length > 1 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 18 }}>
          <Link href="/trends" className={"btn tiny" + (nicheFilter ? "" : " primary")}>All niches</Link>
          {niches.map(n => (
            <Link key={n} href={`/trends?niche=${encodeURIComponent(n)}`}
              className={"btn tiny" + (nicheFilter === n ? " primary" : "")}>
              {n.replace(/_/g, " ")}
            </Link>
          ))}
        </div>
      )}

      {rows.length > 0 ? (
        <div className="steps" style={{ marginTop: 18 }}>
          {rows.map(r => (
            <div className="step" key={r.id}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div style={{ minWidth: 0 }}>
                <h4 style={{ margin: 0 }}>
                  <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: "inherit" }}>{r.title}</a>
                </h4>
                <p style={{ margin: "4px 0 0" }}>
                  <b style={{ color: r.heat >= 70 ? "var(--stuck, #e2483d)" : r.heat >= 45 ? "var(--draft, #fdab3d)" : "var(--dim)" }}>
                    heat {r.heat}
                  </b>
                  {" · "}{PLATFORM_LABEL[r.platform] || r.platform}
                  {r.author ? <> · {r.author}</> : null}
                  {r.engagement > 0 ? <> · {fmt(r.engagement)} engagement</> : null}
                  {r.views > 0 && r.platform === "youtube" ? <> · {fmt(r.views)} views</> : null}
                  {" · "}{ago(r.published_at || r.scraped_at)}
                  {!nicheFilter ? <> · <span className="tag">{r.niche.replace(/_/g, " ")}</span></> : null}
                </p>
              </div>
              <QueueTopic topic={r.title} source={r.url} />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="honest" style={{ marginTop: 18 }}>
            The Scout hasn&apos;t filed its first report yet. It runs on the Railway worker every ~30 min —
            make sure <span className="mono">db/scout.sql</span> has been run in Supabase and the worker is
            deployed. Until then, here is the raw news feed:
          </div>
          <div className="steps" style={{ marginTop: 12 }}>
            {fallback.map((t, i) => (
              <div className="step" key={i}
                style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <h4 style={{ fontWeight: 500 }}>{t}</h4>
                <QueueTopic topic={t} />
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
