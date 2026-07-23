// web/app/dashboard/store/page.tsx
// v5.9.8 REQ-WEB-404: sidebar "Ecommerce · rebrand" pointed here and 404'd.
"use client";
import { useEffect, useState } from "react";

type Product = { id?: string; title: string; price_usd?: number; url?: string; source?: string };

export default function StorePage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/store", { cache: "no-store" })
      .then(r => r.ok ? r.json() : { products: [] })
      .then(j => setProducts(j.products || []))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1>Ecommerce · rebrand</h1>
      <p className="lead">Physical products you sell under your own brand. Content is written to
        feature them where it is honest to do so — never as a forced placement.</p>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>Your products</h3>
        {loading ? <p className="note">Loading…</p>
          : products.length === 0 ? (
          <>
            <p className="note">No products connected yet.</p>
            <p className="note">This module reads from your product library. Until a store is
              connected, content is produced without product placement — which is the correct
              default, not a failure state.</p>
          </>
        ) : (
          <ul>
            {products.map((p, i) => (
              <li key={p.id || i}>
                <b>{p.title}</b>{p.price_usd ? ` — $${p.price_usd}` : ""}
                {p.source && <span className="note"> · {p.source}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <h3>How placement works</h3>
        <p className="note">The monetization step evaluates each finished post against your product
          library. A product is only mentioned when the topic genuinely relates to it. Posts with no
          honest fit ship with no product mention at all.</p>
        <p className="note"><b>You own the store.</b> Connecting a shop here never transfers
          ownership of your storefront, customers, or payment account.</p>
      </div>
    </div>
  );
}
