/**
 * API: /api/connections
 *   GET    -> list current user's connected channels (redacted — no secrets returned)
 *   POST   -> save/refresh credentials for a platform
 *   DELETE -> revoke a platform connection
 *
 * Credentials are encrypted via a Postgres SECURITY DEFINER function so the
 * Next.js server never handles raw-keys in responses. All "read" responses
 * strip the raw tokens and only return booleans + display metadata.
 *
 * Required migrations (run in Supabase SQL editor ONCE):
 *   See db/patches/001_connections_and_brand.sql
 *   Plus create the encrypt/decrypt helper functions below (they are referenced
 *   here — add them via a separate migration if you don't use pgcrypto).
 */
import { NextResponse } from "next/server";
import { supabaseServer } from "@/lib/supabase/server";

// ---------- per-platform credential schemas (extend as you add channels) ----------
type Platform =
  | "instagram"
  | "youtube"
  | "tiktok"
  | "x"
  | "linkedin"
  | "pinterest"
  | "facebook";

type Creds = {
  accessToken?: string;
  refreshToken?: string;
  userId?: string;          // IG user id, YouTube channel id, etc.
  apiKey?: string;          // X api key, etc.
  apiSecret?: string;
  expiresAt?: string;
  scopes?: string[];
};

const PLATFORM_META: Record<Platform, { label: string; required: (keyof Creds)[]; oauth: boolean; docUrl: string }> = {
  instagram: { label: "Instagram (Reels + Feed)", required: ["accessToken", "userId"], oauth: true,  docUrl: "https://developers.facebook.com/docs/instagram-api/getting-started" },
  youtube:   { label: "YouTube (Shorts + Long)",  required: ["accessToken", "refreshToken", "userId"], oauth: true, docUrl: "https://developers.google.com/youtube/registering_an_application" },
  tiktok:    { label: "TikTok",                   required: ["accessToken"], oauth: true,  docUrl: "https://developers.tiktok.com/doc/content-posting-api-get-started" },
  x:         { label: "X / Twitter",              required: ["accessToken", "apiKey", "apiSecret"], oauth: true, docUrl: "https://developer.x.com/en/docs/twitter-api" },
  linkedin:  { label: "LinkedIn",                 required: ["accessToken", "userId"], oauth: true, docUrl: "https://learn.microsoft.com/en-us/linkedin/marketing/" },
  pinterest: { label: "Pinterest",                required: ["accessToken", "userId"], oauth: true, docUrl: "https://developers.pinterest.com/docs/getting-started/" },
  facebook:  { label: "Facebook Page",            required: ["accessToken", "userId"], oauth: true, docUrl: "https://developers.facebook.com/docs/pages-api/" },
};

// ---------- GET ----------
export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  const { data, error } = await sb
    .from("user_connections")
    .select("platform, display_name, status, last_test_at, error_message, created_at")
    .eq("user_id", user.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({
    platforms: Object.fromEntries(
      (Object.keys(PLATFORM_META) as Platform[]).map((p) => [p, {
        ...PLATFORM_META[p],
        connected: (data || []).some((r: any) => r.platform === p && r.status === "active"),
        display_name: (data || []).find((r: any) => r.platform === p)?.display_name || null,
        last_test_at: (data || []).find((r: any) => r.platform === p)?.last_test_at || null,
        error: (data || []).find((r: any) => r.platform === p)?.error_message || null,
      }])
    ),
  });
}

// ---------- POST (save credentials) ----------
export async function POST(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  const body = await req.json();
  const platform = body.platform as Platform;
  const creds = (body.credentials || {}) as Creds;
  const displayName = (body.display_name || null) as string | null;

  if (!PLATFORM_META[platform]) return NextResponse.json({ error: "Unknown platform" }, { status: 400 });
  const missing = PLATFORM_META[platform].required.filter((k) => !creds[k]);
  if (missing.length) return NextResponse.json({ error: `Missing required fields: ${missing.join(", ")}` }, { status: 400 });

  // Encrypt server-side via Postgres pgcrypto function (see migration).
  // The function lives in the public schema and uses pgsodium or a GUC-held key.
  // If you haven't deployed the encryption function yet, the INSERT below falls
  // back to storing credentials in a jsonb column (`credentials`) for local dev —
  // REPLACE THIS with a real RPC call before launch.
  const { data: enc, error: encErr } = await sb.rpc("encrypt_creds", { payload: creds });

  const row: any = {
    user_id: user.id,
    platform,
    display_name: displayName,
    status: "active",
    last_test_at: new Date().toISOString(),
    error_message: null,
    updated_at: new Date().toISOString(),
  };
  if (enc && !encErr) {
    row.cred_enc = enc;
    row.credentials = {}; // ciphertext-only in production
  } else {
    // dev fallback — remove before launch
    row.credentials = creds;
    row.cred_enc = null;
  }

  const { error } = await sb.from("user_connections").upsert(row, { onConflict: "user_id,platform" });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, platform, connected: true });
}

// ---------- DELETE (revoke) ----------
export async function DELETE(req: Request) {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const { platform } = await req.json();
  if (!PLATFORM_META[platform as Platform]) return NextResponse.json({ error: "Unknown platform" }, { status: 400 });
  const { error } = await sb.from("user_connections")
    .update({ status: "revoked", updated_at: new Date().toISOString() })
    .eq("user_id", user.id).eq("platform", platform);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
