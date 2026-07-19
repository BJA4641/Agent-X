import { redirect } from "next/navigation";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import SettingsPanel from "@/components/SettingsPanel";
import AdminActions from "@/components/AdminActions";

export const dynamic = "force-dynamic";

export default async function ConsolePage() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) redirect("/login");
  if (!isAdmin(user.email)) redirect("/dashboard");
  const admin = supabaseAdmin();

  const TENANT = "me";
  const { data: settings } = await admin.from("settings").select("key,value")
    .eq("tenant_id", TENANT).in("key", ["model", "daily_budget"]);
  const model = settings?.find((s) => s.key === "model")?.value || {};
  const budget = settings?.find((s) => s.key === "daily_budget")?.value?.usd;

  const today = new Date(); today.setHours(0,0,0,0);
  const { data: spendRows } = await admin.from("run_ledger").select("cost_usd")
    .eq("tenant_id", TENANT).gte("created_at", today.toISOString());
  const spent = (spendRows || []).reduce((a: number, r: any) => a + Number(r.cost_usd || 0), 0);

  return (
    <div>
      <h1>Developer console</h1>
      <p className="note" style={{ maxWidth: 680 }}>
        <b>Admin only.</b> AI engine choice, API keys (set in Vercel/Railway env vars),
        daily spend cap, kill switch. Regular users never see this — they only connect
        their own social accounts and spend credits.
      </p>

      <div className="honest" style={{ marginTop: 16 }}>
        <b>API keys are set as environment variables in Vercel (web) and Railway (pipeline) — not in the database.</b>
        Required keys: ANTHROPIC_API_KEY (scripts+strategy), GEMINI_API_KEY (images),
        SUPABASE_SERVICE_ROLE_KEY. Optional: ELEVENLABS_API_KEY, OPENROUTER_API_KEY,
        GROQ_API_KEY, STRIPE_SECRET_KEY.
      </div>

      <div style={{ marginTop: 28 }}>
        <SettingsPanel
          isAdmin={true}
          initialProvider={model.provider || "anthropic"}
          initialModel={model.model || ""}
          initialBudget={typeof budget === "number" ? budget : 1.5}
          spentToday={spent}
        />
      </div>

      <div style={{ marginTop: 28 }}>
        <AdminActions />
      </div>
    </div>
  );
}
