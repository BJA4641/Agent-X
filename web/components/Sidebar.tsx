"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Item = { href: string; label: string; tag?: string };
type Group = { label: string; items: Item[] };

export default function Sidebar({ admin }: { admin: boolean }) {
  const path = usePathname();
  const groups: Group[] = [
    { label: "Social media platforms", items: [
      { href: "/dashboard/instagram", label: "Instagram", tag: "open" },
      { href: "/dashboard/youtube", label: "YouTube", tag: "next" },
      { href: "/dashboard/tiktok", label: "TikTok", tag: "manual" },
    ]},
    { label: "Ecommerce", items: [
      { href: "/dashboard/store", label: "Store rebranding" },
    ]},
  ];
  if (admin) groups.push({ label: "Automation", items: [
    { href: "/studio", label: "Studio · production" },
    { href: "/trends", label: "Trends · scout desk" },
  ]});
  const on = (href: string) => (href === "/dashboard" ? path === href : path.startsWith(href));
  return (
    <aside className="sidebar">
      <Link href="/dashboard" className={"sideitem" + (path === "/dashboard" ? " on" : "")}>Overview</Link>
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
