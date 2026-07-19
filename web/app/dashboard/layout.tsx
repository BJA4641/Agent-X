import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";
import RightPanel from "@/components/RightPanel";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) redirect("/login");
  const admin = isAdmin(user.email);

  let onboarded = false;
  try {
    const adminSb = supabaseAdmin();
    const { data: profile } = await adminSb
      .from("profiles").select("onboarded").eq("user_id", user.id).maybeSingle();
    onboarded = !!(profile?.onboarded);
  } catch { onboarded = false; }

  return (
    <>
      <header className="site"><div className="wrap">
        <Link href="/dashboard" className="logo" style={{ textDecoration: "none" }}>Agent<b>-X</b></Link>
        <nav className="top">
          {admin && <Link href="/studio">Studio</Link>}
          {admin && <Link href="/trends">Trends</Link>}
          <Link href="/dashboard">Dashboard</Link>
          <span style={{ marginLeft: 24, color: "var(--dim)", fontSize: 14 }}>{user.email}</span>
          <ThemeToggle />
        </nav>
      </div></header>
      <div className="wrap shell" style={{ display: "grid", gridTemplateColumns: "220px minmax(0,1fr) 300px", gap: 32, alignItems: "start" }}>
        <Sidebar admin={admin} onboarded={onboarded} />
        <main className="shellmain">{children}</main>
        <RightPanel />
      </div>
    </>
  );
}
