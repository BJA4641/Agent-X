import { redirect } from "next/navigation";
import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";
import Sidebar from "@/components/Sidebar";

export default async function StudioLayout({ children }: { children: React.ReactNode }) {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) redirect("/login");
  const { data: { user } } = await supabaseServer().auth.getUser();
  if (!user) redirect("/login");
  return (
    <>
      <header className="site"><div className="wrap">
        <Link href="/" className="logo" style={{ textDecoration: "none" }}>Agent<b>-X</b> <span className="tag" style={{ marginLeft: 8 }}>studio</span></Link>
        <nav className="top"><span style={{ color: "var(--dim)", fontSize: 14 }}>{user.email}</span></nav>
      </div></header>
      <div className="wrap shell">
        <Sidebar admin={isAdmin(user.email)} />
        <main className="shellmain">{children}</main>
      </div>
    </>
  );
}
