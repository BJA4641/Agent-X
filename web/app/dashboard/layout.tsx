import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import Sidebar from "@/components/Sidebar";
import ThemeToggle from "@/components/ThemeToggle";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user) redirect("/login");
  const admin = isAdmin(user.email);
  return (
    <>
      <header className="site"><div className="wrap">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>build<b>along</b></Link>
        <nav className="top">{admin && <Link href="/studio">Studio</Link>}<span style={{ marginLeft: 24, color: "var(--dim)", fontSize: 14 }}>{user.email}</span><ThemeToggle /></nav>
      </div></header>
      <div className="wrap shell">
        <Sidebar admin={admin} />
        <main className="shellmain">{children}</main>
      </div>
    </>
  );
}
