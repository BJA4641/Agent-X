import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) redirect("/login");
  const admin = isAdmin(user.email);

  // Onboarding gate: if the profiles table hasn't been created yet (pre-v1.4 DB)
  // we let them in rather than erroring. Once setup_v1.4.sql is run, new users
  // who haven't picked a niche are sent to /onboarding.
  let onboarded = true;
  try {
    const adminSb = supabaseAdmin();
    const { data: profile } = await adminSb
      .from("profiles")
      .select("onboarded")
      .eq("user_id", user.id)
      .maybeSingle();
    if (!profile?.onboarded) onboarded = false;
  } catch {
    onboarded = true; // table doesn't exist yet; don't block
  }
  if (!onboarded) redirect("/onboarding");

  return (
    <>
      <header className="site"><div className="wrap">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>Agent<b>-X</b></Link>
        <nav className="top">{admin && <Link href="/studio">Studio</Link>}<span style={{ marginLeft: 24, color: "var(--dim)", fontSize: 14 }}>{user.email}</span><ThemeToggle /></nav>
      </div></header>
      <div className="wrap shell">
        <Sidebar admin={admin} onboarded={onboarded} />
        <main className="shellmain">{children}</main>
      </div>
    </>
  );
}
