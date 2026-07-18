/**
 * /api/connections — GET / POST / DELETE for per-user channel tokens.
 * Secrets are encrypted via the Postgres encrypt_token() function (defined
 * in db/setup_v1.4.sql) BEFORE they hit the table; the raw secret is NEVER
 * returned to the browser.
 */
import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";

type Platform = "instagram" | "youtube" | "tiktok" | "x" | "linkedin" | "pinterest" | "facebook";

type Creds = Record<string, string>;

const PLATFORM_META: Record<Platform, {
  label: string;
  required: (keyof Creds)[];
  oauth: boolean;
  docUrl: string;
  blurb: string;
}> = {
  instagram: {
    label: "Instagram (Reels + Feed)",
    required: ["accessToken", "userId"],
    oauth: true,
    docUrl: "https://developers.facebook.com/docs/instagram-api/getting-started",
    blurb: "Auto-post Reels via the Meta Graph API once your app is approved. Until then, copy captions and videos from Studio and post manually.",
  },
  youtube: {
    label: "YouTube Shorts",
    required: ["accessToken", "refreshToken", "userId"],
    oauth: true,
    docUrl: "https://developers.google.com/youtube/registering_an_application",
    blurb: "Shorts upload via the YouTube Data API. Needs a Google Cloud OAuth client.",
  },
  tiktok: {
    label: "TikTok",
    required: ["accessToken"],
    oauth: true,
    docUrl: "https://developers.tiktok.com/doc/content-posting-api-get-started",
    blurb: "Content Posting API available to Business accounts. Manual upload mode is the default until approved.",
  },
  x: {
    label: "X / Twitter",
    required: ["accessToken", "apiKey", "apiSecret"],
    oauth: true,
    docUrl: "https://developer.x.com/en/docs/twitter-api",
    blurb: "Posts and threads via the X API v2.",
  },
  linkedin: {
    label: "LinkedIn",
    required: ["accessToken", "userId"],
    oauth: true,
    docUrl: "https://learn.microsoft.com/en-us/linkedin/marketing/",
    blurb: "Personal and company-page posts for B2B content.",
  },
  pinterest: {
    label: "Pinterest",
    required: ["accessToken", "userId"],
    oauth: true,
    docUrl: "https://developers.pinterest.com/docs/getting-started/",
    blurb: "Pins drive long-tail search traffic. Best for visual niches.",
  },
  facebook: {
    label: "Facebook Page",
    required: ["accessToken", "userId"],
    oauth: true,
    docUrl: "https://developers.facebook.com/docs/pages-api/",
    blurb: "Cross-post Reels/feed to a connected Facebook Page.",
  },
};

export async function GET() {
  const sb = supabaseServer();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  // Run setup first? If the table doesn't exist we return a clean error.
  const admin = supabaseAdmin();
  const { data: rows, error } = await admin
    .from("user_connections")
    .select("platform,display_name,status,last_test_at,error_message,credentials_json")
    .eq("user_id", user.id);

  if (error) {
    return NextResponse.json({
      error: `Connections table not found. Run db/setup_v1.4.sql in Supabase first. (${error.message})`,
      platforms: {},
    }, { status: 503 });
  }

  const platforms: Record<string, any> = {};
  (Object.keys(PLATFORM_META) as Platform[]).forEach((p) => {
    const meta = PLATFORM_META[p];
    const row = (rows || []).find((r: any) => r.platform === p);
    const connected = !!row && row.status === "active";
    platforms[p] = {
      ...meta,
      connected,
      display_name: row?.display_name || row?.credentials_json?.username || null,
      last_test_at: row?.last_test_at || null,
      error: row?.error_message || null,
    };
  });
  return NextResponse.json({ platforms });
}

export async function POST(req: Request) {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });

  const body = await req.json();
  const platform = body.platform as Platform;
  const creds = (body.credentials || {}) as Creds;
  const displayName = (body.display_name || null) as string | null;
  if (!PLATFORM_META[platform]) return NextResponse.json({ error: "Unknown platform" }, { status: 400 });

  const missing = PLATFORM_META[platform].required.filter((k) => !creds[k]);
  if (missing.length) return NextResponse.json({ error: `Missing: ${missing.join(", ")}` }, { status: 400 });

  // Encrypt the credentials server-side via the Postgres RPC function.
  const plainString = JSON.stringify(creds);
  const { data: enc, error: encErr } = await admin.rpc("encrypt_token", { plain: plainString });
  if (encErr) return NextResponse.json({ error: `Encryption failed — run setup_v1.4.sql first. (${encErr.message})` }, { status: 500 });

  // Non-secret summary (account id, username) stays queryable for the UI.
  const publicSummary: Record<string, any> = {};
  if (creds.userId) publicSummary.account_id = creds.userId;
  if (displayName) publicSummary.username = displayName;

  const { error } = await admin.from("user_connections").upsert({
    user_id: user.id,
    platform,
    display_name: displayName,
    credentials_json: publicSummary,
    cred_enc: enc,
    status: "active",
    last_test_at: new Date().toISOString(),
    error_message: null,
    updated_at: new Date().toISOString(),
  }, { onConflict: "user_id,platform" });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, platform, connected: true });
}

export async function DELETE(req: Request) {
  const sb = supabaseServer();
  const admin = supabaseAdmin();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  const { platform } = await req.json();
  if (!PLATFORM_META[platform as Platform]) return NextResponse.json({ error: "Unknown platform" }, { status: 400 });
  const { error } = await admin.from("user_connections")
    .update({ status: "revoked", updated_at: new Date().toISOString() })
    .eq("user_id", user.id).eq("platform", platform);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
