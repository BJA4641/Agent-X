import Link from "next/link";
import { TRACKS } from "@/lib/tracks";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

export default async function Dashboard() {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  const { data: ents } = await sb.from("entitlements").select("module_id");
  const owned = new Set((ents || []).map((e) => e.module_id));

  // Check if user has completed any setup (niche or wallet or connections).
  // If nothing yet, show a friendly setup card at the top — but NEVER redirect.
  let setupState: "none" | "partial" | "done" = "none";
  try {
    const [{ data: profile }, { data: wallet }] = await Promise.all([
      admin.from("profiles").select("onboarded,niche").eq("user_id", user!.id).maybeSingle(),
      admin.from("wallets").select("balance_usd").eq("user_id", user!.id).maybeSingle(),
    ]);
    if (profile?.onboarded && wallet) setupState = "done";
    else if (profile?.niche || wallet) setupState = "partial";
  } catch {
    setupState = "none";
  }

  // Seed wallet if missing (gives $1 welcome the first time dashboard loads)
  if (setupState !== "done") {
    try {
      const { data: existing } = await admin.from("wallets").select("user_id").eq("user_id", user!.id).maybeSingle();
      if (!existing) {
        await admin.from("wallets").insert({ user_id: user!.id, balance_usd: 1.0, lifetime_topup: 1.0 });
        await admin.from("wallet_transactions").insert({
          user_id: user!.id, type: "bonus", amount: 1.0, note: "Welcome bonus",
        });
      }
      // Create a profile row if missing (marks as created but not fully onboarded)
      const { data: p } = await admin.from("profiles").select("user_id").eq("user_id", user!.id).maybeSingle();
      if (!p) {
        await admin.from("profiles").insert({
          user_id: user!.id,
          display_name: user!.email?.split("@")[0] || "Creator",
          onboarded: false, onboarding_step: 0,
        });
      }
    } catch {}
  }

  return (
    <>
      <h2>Your income tracks</h2>
      <p className="lead">
        Each track is a verified path to real money. Start with ONE — don't open them all at once.
        Pick the money method that matches what you already want to build, follow the checkboxes, and ship.
      </p>

      {setupState !== "done" && (
        <div className="card" style={{
          marginTop: 20, borderColor: "var(--draft)",
          background: "linear-gradient(180deg, rgba(255,200,80,0.06), transparent)"
        }}>
          <h3>👋 Welcome — set up your workspace (optional, 2 minutes)</h3>
          <p style={{ marginBottom: 12 }}>
            You can open any track below right now and follow the steps. If you plan to start with
            social content (Reels/Shorts/TikToks), tell us your niche first so the AI agents can
            suggest topics, hooks, and trend angles tailored to you. If you're starting with
            ecommerce or affiliate only, you can skip this.
          </p>
          <p style={{ display: "flex", gap: 12, alignItems: "center", margin: 0 }}>
            <Link href="/onboarding" className="cta" style={{ display: "inline-block" }}>
              Set up content niche →
            </Link>
            <Link href="/dashboard/store" style={{ color: "var(--dim)" }}>I'll start with ecommerce instead</Link>
            <Link href="/dashboard/affiliate" style={{ color: "var(--dim)" }}>I'll start with affiliate</Link>
          </p>
        </div>
      )}

      <div className="grid3" style={{ marginTop: 24 }}>
        {TRACKS.map((t) => {
          const open = t.price === 0 || owned.has(t.id);
          return (
            <div className="card" key={t.id}>
              <p style={{ marginBottom: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className={t.state === "live" ? "tag live" : "tag"}>{t.state === "live" ? "open" : "coming next"}</span>
                <span className="mono" style={{ fontSize: 12, color: "var(--dim)" }}>{t.price === 0 ? "free" : `$${t.price}`}</span>
              </p>
              <h3>{t.name}</h3>
              <p style={{ color: "var(--approved)", fontSize: 13, marginBottom: 8 }}>💰 {t.incomeLayer}</p>
              <p>{t.blurb}</p>
              <p style={{ marginTop: 14 }}>
                {open && t.state === "live"
                  ? <Link href={`/dashboard/${t.id}`} style={{ color: "var(--scheduled)" }}>Open track →</Link>
                  : <span className="note">{t.state === "soon" ? "Module ships next — finish your first live track to unlock early access." : ""}</span>}
              </p>
            </div>
          );
        })}
      </div>
      <div className="honest" style={{ marginTop: 28 }}>
        <b>Rule #1 of the dashboard:</b> pick ONE track and finish its checkboxes before opening the next.
        Spreading yourself across 5 platforms at day 5 is the #1 reason beginners earn zero.
        Ship. Earn. Then expand.
      </div>
    </>
  );
}
