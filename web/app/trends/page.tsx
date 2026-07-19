import { redirect } from "next/navigation";
import { supabaseServer } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import QueueTopic from "@/components/QueueTopic";

export const dynamic = "force-dynamic";

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

// Decode HTML entities (&amp;, &quot;, &#39;, &lt;, &gt;, numeric) so titles read correctly
function decodeHtml(s: string): string {
  if (!s) return s;
  return s
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
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

type Outlier = { title: string; url: string; views: number; ratio: number; channel: string };

function outliers(xml: string): Outlier[] {
  const channel = decodeHtml((xml.match(/<title>(.*?)<\/title>/) || [])[1] || "channel");
  const entries = xml.split("<entry>").slice(1);
  const vids = entries.map(e => ({
    title: decodeHtml((e.match(/<title>(.*?)<\/title>/) || [])[1] || ""),
    url: (e.match(/<link rel="alternate" href="(.*?)"/) || [])[1] || "#",
    views: parseInt((e.match(/views="(\d+)"/) || [])[1] || "0", 10),
  })).filter(v => v.views > 0);
  if (vids.length < 4) return [];
  const med = [...vids].sort((a, b) => a.views - b.views)[Math.floor(vids.length / 2)].views || 1;
  return vids.filter(v => v.views >= 2 * med).map(v => ({ ...v, ratio: v.views / med, channel }));
}

export default async function Trends() {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user) redirect("/login");
  if (!isAdmin(user.email)) redirect("/dashboard");

  const channelIds = (process.env.COMPETITOR_CHANNELS || "").split(",").map(s => s.trim()).filter(Boolean);
  const [newsXml, compXml] = await Promise.all([
    Promise.all(FEEDS.map(fetchText)),
    Promise.all(channelIds.map(id => fetchText(`https://www.youtube.com/feeds/videos.xml?channel_id=${id}`))),
  ]);
  const seen = new Set<string>();
  const news = newsXml.flatMap(headlines).filter(t => t.length > 15 && !seen.has(t.toLowerCase()) && seen.add(t.toLowerCase())).slice(0, 14);
  const proven = compXml.flatMap(outliers).sort((a, b) => b.ratio - a.ratio).slice(0, 12);

  return (
    <>
      <h2>Trend scout desk</h2>
      <p className="lead">What is working in your niche right now. <b>Queue my version</b> drops a topic on the Studio board as an idea — the writer produces an <i>original</i> script on the proven pattern (topic + angle), never a repost. That is the version platforms reward and the one that survives YouTube&apos;s inauthentic-content rules.</p>

      <div style={{ marginTop: 28 }}>
        <h3>Proven outliers — competitor videos beating their own average</h3>
        {channelIds.length === 0 ? (
          <div className="honest" style={{ marginTop: 10 }}>Not configured yet. Add <span className="mono">COMPETITOR_CHANNELS=UCxxx,UCyyy</span> in Vercel (for this desk) and Railway (for the planner) — then this section fills with every competitor video doing 2× or more above that channel&apos;s median.</div>
        ) : proven.length === 0 ? (
          <div className="honest" style={{ marginTop: 10 }}>No 2×+ outliers in the tracked channels&apos; recent uploads. That is normal most weeks — outliers are rare by definition.</div>
        ) : (
          <div className="steps" style={{ marginTop: 12 }}>
            {proven.map((o, i) => (
              <div className="step" key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                <div>
                  <h4><a href={o.url} target="_blank" style={{ color: "inherit" }}>{o.title}</a></h4>
                  <p>{o.channel} · {o.views.toLocaleString()} views · <b style={{ color: "var(--approved)" }}>{o.ratio.toFixed(1)}× their median</b></p>
                </div>
                <QueueTopic topic={o.title} source={o.url} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ marginTop: 32 }}>
        <h3>This week in the niche — fresh headlines</h3>
        <p className="note">Same feed the strategist reads. Queue anything you want covered before everyone else covers it.</p>
        <div className="steps" style={{ marginTop: 12 }}>
          {news.map((t, i) => (
            <div className="step" key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <h4 style={{ fontWeight: 500 }}>{t}</h4>
              <QueueTopic topic={t} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
