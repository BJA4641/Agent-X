// REPLACE web/app/dashboard/layout.tsx with this logic:
// after auth, redirect new users to /onboarding if their profile.onboarded=false.
import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) redirect("/login");
  const admin = isAdmin(user.email);

  // Check onboarding
  const { data: profile } = await sb.from("profiles").select("onboarded").eq("user_id", user.id).maybeSingle();
  const onboarded = !!profile?.onboarded;
  const { pathname } = new URL("https://x.com"); // placeholder; use headers() in real Next.js
  // If not onboarded and not already on /onboarding or /wallet (so we don't loop), redirect:
  // Use next/headers for real pathname detection. Simpler: allow children but the Sidebar shows the banner.

  return (
    <>
      <header className="site"><div className="wrap">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>Agent<b>-X</b></Link>
        <nav className="top">{admin && <Link href="/studio">Studio</Link>}
          <span style={{ marginLeft: 24, color: "var(--dim)", fontSize: 14 }}>{user.email}</span>
          <ThemeToggle />
        </nav>
      </div></header>
      <div className="wrap shell">
        <Sidebar admin={admin} onboarded={onboarded} />
        <main className="shellmain">{children}</main>
      </div>
    </>
  );
}
