// web/app/dashboard/digital/page.tsx
// v5.9.8 REQ-WEB-404: sidebar "Digital products" pointed here and 404'd.
"use client";
import { useEffect, useState } from "react";

type Item = { id?: string; title: string; price_usd?: number; kind?: string; url?: string };

export default function DigitalPage() {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/digital", { cache: "no-store" })
      .then(r => r.ok ? r.json() : { items: [] })
      .then(j => setItems(j.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1>Digital products</h1>
      <p className="lead">Guides, templates, presets and courses you sell directly. Highest margin
        of any monetization path — no inventory, no shipping, no returns.</p>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Your catalogue</h3>
        {loading ? <p className="note">Loading…</p>
          : items.length === 0 ? (
          <p className="note">Nothing listed yet. Digital products work best once an account has an
            audience — build the content habit first, then sell to the audience it earns.</p>
        ) : (
          <ul>
            {items.map((it, i) => (
              <li key={it.id || i}>
                <b>{it.title}</b>{it.price_usd ? ` — $${it.price_usd}` : ""}
                {it.kind && <span className="note"> · {it.kind}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Claims policy</h3>
        <p className="note">Product copy generated here never states or implies income results.
          No "make $X per month", no earnings screenshots, no guarantees. This is a hard rule in the
          writer, not a preference — it protects both the accounts and the buyers.</p>
      </div>
    </div>
  );
}
