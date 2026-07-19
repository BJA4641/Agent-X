"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; label: string; tag?: string };
type Group = { label: string; items: Item[] };

export default function Sidebar({ admin, onboarded }: { admin: boolean; onboarded?: boolean }) {
  const path = usePathname();
  const groups: Group[] = [
    { label: "Create", items: [
      { href: "/dashboard/studio", label: "Studio · production", tag: admin ? "admin" : undefined },
      { href: "/dashboard/workspace", label: "Agent workspace" },
      { href: "/dashboard/clone", label: "Clone viral" },
      { href: "/dashboard/trends", label: "Trends · scout desk", tag: admin ? "admin" : undefined },
    ]},
    { label: "Social platforms", items: [
      { href: "/dashboard/instagram", label: "Instagram" },
      { href: "/dashboard/youtube", label: "YouTube" },
      { href: "/dashboard/tiktok", label: "TikTok" },
      { href: "/dashboard/affiliate", label: "Affiliate links" },
    ]},
    { label: "Monetize", items: [
      { href: "/dashboard/store", label: "Ecommerce · rebrand" },
      { href: "/dashboard/digital", label: "Digital products" },
    ]},
    { label: "Account", items: [
      { href: "/dashboard/wallet", label: "Wallet & billing" },
      { href: "/dashboard/models", label: "AI models" },
      { href: "/dashboard/settings", label: "Settings" },
    ]},
  ];
  if (admin) { /* admin-only items tagged above */ }
  const on = (href: string) => path === href || (href !== "/dashboard" && path.startsWith(href));
  return (
    <aside className="sidebar">
      <Link href="/dashboard" className={"sideitem" + (path === "/dashboard" ? " on" : "")}>Overview</Link>
      {!onboarded && (
        <Link href="/dashboard/onboarding" className="sideitem on" style={{ borderLeft: "3px solid var(--draft)" }}>
          → Finish setup
        </Link>
      )}
      {groups.map(g => (
        <div className="sidegroup" key={g.label}>
          <h5>{g.label}</h5>
          {g.items.map(it => (
            <Link key={it.href} href={it.href} className={"sideitem" + (on(it.href) ? " on" : "")}>
              {it.label}{it.tag && <span className="sidetag">{it.tag}</span>}
            </Link>
          ))}
        </div>
      ))}
    </aside>
  );
}
