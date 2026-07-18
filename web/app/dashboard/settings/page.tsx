import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import SettingsPanel from "@/components/SettingsPanel";
import ChannelConnections from "@/components/ChannelConnections";

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
      <p className="note" style={{ maxWidth: 720, marginBottom: 12 }}>
        Connect each account you want Agent-X to post to. Tokens are encrypted at rest
        and the worker only reads them server-side. Instagram auto-posting works once your
        Meta app is approved; until then Studio prepares everything and one click copies
        the caption/video for manual upload.
      </p>
      <ChannelConnections />

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
