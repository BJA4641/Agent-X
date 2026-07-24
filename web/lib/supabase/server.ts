import { createServerClient } from "@supabase/ssr";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

/**
 * v5.11.0 REQ-NOCACHE-DB — every Supabase read must hit the database.
 *
 * The bug this fixes, caught 2026-07-24 from a live /api/version response:
 *   top-level worker  -> host 24678e1868d7, version 5.8.8,  age 35143s
 *   diag.workers[0]   -> host 7eb13f652775, version 5.10.5, age  3214s
 *   actual DB row     -> host 8a74bd06c517, version 5.10.9, age     1s
 * Two different answers from ONE table inside ONE response, neither of them
 * true. The supabase-js client calls global fetch(); Next.js caches fetch
 * results per unique request, so each distinct query froze at a different
 * moment and then served that snapshot indefinitely.
 *
 * Consequences that are now explained: a banner insisting the worker was dead
 * for ten hours while it beat every second, a Spend card frozen at an old
 * figure, and drafts appearing late. `dynamic = "force-dynamic"` does NOT
 * cover this — it governs the ROUTE, not the fetches inside it.
 *
 * Fix: hand supabase-js a fetch that always sets cache: "no-store".
 */
const noStoreFetch: typeof fetch = (input: any, init?: any) =>
  fetch(input, { ...(init || {}), cache: "no-store" });

export function supabaseServer() {
  const store = cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { global: { fetch: noStoreFetch },
      cookies: {
        getAll: () => store.getAll(),
        setAll: (list: { name: string; value: string; options?: any }[]) => {
          try { list.forEach(({ name, value, options }) => store.set(name, value, options)); } catch {}
        },
    }});
}

export function supabaseAdmin() {
  return createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false }, global: { fetch: noStoreFetch } });
}
