import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import SettingsPanel from "@/components/SettingsPanel";

const TENANT = "me";

export default async function SettingsPage() {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  const admins = (process.env.ADMIN_EMAILS || "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
  const isAdmin = !!user?.email && admins.includes(user.email.toLowerCase());

  const { data: settings } = await admin.from("settings").select("key,value")
    .eq("tenant_id", TENANT).in("key", ["model", "daily_budget"]);
  const model = settings?.find((s) => s.key === "model")?.value || {};
  const budget = settings?.find((s) => s.key === "daily_budget")?.value?.usd;

  const today = new Date(); today.setHours(0, 0, 0, 0);
  const { data: spendRows } = await admin.from("run_ledger").select("cost_usd")
    .eq("tenant_id", TENANT).gte("created_at", today.toISOString());
  const spent = (spendRows || []).reduce((a, r) => a + Number(r.cost_usd || 0), 0);

  return (
    <div>
      <h1>Settings</h1>
      <p className="note" style={{ maxWidth: 640 }}>
        Connections, AI engine, and spend controls for your factory.
      </p>

      <h2 style={{ marginTop: 28 }}>Channel connections</h2>
      <div className="grid">
        <div className="card">
          <h3>Instagram</h3>
          <p className="note">
            Auto-posting uses Meta&apos;s official API. Your access token and account ID live as
            worker variables (<span className="mono">IG_ACCESS_TOKEN</span>, <span className="mono">IG_USER_ID</span> on Railway) —
            Module 6 of the Instagram course walks you through getting them. Until Meta approves the app,
            the Studio prepares everything and you post with one copy-paste.
          </p>
        </div>
        <div className="card">
          <h3>YouTube</h3>
          <p className="note">
            Shorts upload keys (<span className="mono">YT_CLIENT_ID</span>, <span className="mono">YT_CLIENT_SECRET</span>,{" "}
            <span className="mono">YT_REFRESH_TOKEN</span>) arrive with the YouTube course track. The same videos
            the Studio renders for Reels work as Shorts today via download → upload.
          </p>
        </div>
        <div className="card">
          <h3>TikTok</h3>
          <p className="note">
            Manual by design — TikTok&apos;s API restricts auto-posting for new apps, and native uploads perform
            better anyway. The <a href="/dashboard/tiktok">TikTok page</a> gives you the download + caption + sound flow.
          </p>
        </div>
      </div>
      <p className="note" style={{ marginTop: 8 }}>
        One-click per-user OAuth connections ship with the multi-user SaaS version — for now, connections are
        factory-level variables so your token never touches the browser.
      </p>

      <SettingsPanel
        isAdmin={isAdmin}
        initialProvider={model.provider || "anthropic"}
        initialModel={model.model || ""}
        initialBudget={typeof budget === "number" ? budget : 1.5}
        spentToday={spent}
      />
    </div>
  );
}
