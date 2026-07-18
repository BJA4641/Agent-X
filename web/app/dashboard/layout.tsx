import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

export default async function DashLayout({ children }: { children: React.ReactNode }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user) redirect("/login");
  return (
    <>
      <header className="site"><div className="wrap">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>build<b>along</b></Link>
        <nav className="top"><Link href="/dashboard">Tracks</Link>{isAdmin(user.email) && <Link href="/studio" style={{ marginLeft: 24 }}>Studio</Link>}<span style={{ marginLeft: 24, color: "var(--dim)", fontSize: 14 }}>{user.email}</span></nav>
      </div></header>
      <main className="wrap" style={{ padding: "40px 24px" }}>{children}</main>
    </>
  );
}
