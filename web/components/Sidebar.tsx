"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; label: string; tag?: string };
type Group = { label: string; items: Item[] };

export default function Sidebar({ admin, onboarded }: { admin: boolean; onboarded?: boolean }) {
  const path = usePathname();
  const groups: Group[] = [
    { label: "Create", items: [
      { href: "/studio", label: "Studio · production", tag: admin ? "admin" : undefined },
      { href: "/workspace", label: "Agent workspace" },
      { href: "/clone", label: "Clone viral" },
      { href: "/trends", label: "Trends · scout desk", tag: admin ? "admin" : undefined },
    ]},
    { label: "Social media platforms", items: [
      { href: "/dashboard/instagram", label: "Instagram", tag: "open" },
      { href: "/dashboard/youtube", label: "YouTube", tag: "next" },
      { href: "/dashboard/tiktok", label: "TikTok", tag: "manual" },
    ]},
    { label: "Monetize", items: [
      { href: "/wallet", label: "Wallet & billing" },
      { href: "/dashboard/store", label: "Store rebranding" },
      { href: "/dashboard/affiliate", label: "Affiliate links" },
    ]},
    { label: "Account", items: [
      { href: "/dashboard/models", label: "Models · leaderboard" },
      { href: "/dashboard/settings", label: "Settings" },
    ]},
  ];
  if (admin) {
    // admin-only items already tagged above
  }
  const on = (href: string) => path === href || (href !== "/dashboard" && path.startsWith(href));
  return (
    <aside className="sidebar">
      <Link href="/dashboard" className={"sideitem" + (path === "/dashboard" ? " on" : "")}>Overview</Link>
      {!onboarded && (
        <Link href="/onboarding" className="sideitem on" style={{ borderLeft: "3px solid var(--draft)" }}>
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
