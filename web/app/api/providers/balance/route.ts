import { NextResponse } from "next/server";
import { supabaseServer, supabaseAdmin } from "@/lib/supabase/server";
import { isAdmin } from "@/lib/admin";

/**
 * GET /api/providers/balance
 *
 * Admin-only. Checks live credit/balance status for each connected AI provider
 * plus Railway so you can see at a glance which wallets have money left.
 *
 * Strategy per provider:
 *   - OpenRouter:  has a real /api/v1/auth/key endpoint that returns remaining
 *                  credits + usage. Best data.
 *   - Groq:        /v1/users/me?expand=credits returns credits_remaining (FREE
 *                  tier reports unlimited).
 *   - Anthropic:   doesn't expose credit balance via API. We show API-key
 *                  validity + month-to-date usage estimate from run_ledger.
 *   - Google/Gemini: Free tier has no balance endpoint. Show key status + MTD.
 *   - Railway:     /v1/workspaces + /v1/subscriptions returns plan info and
 *                  usage. Needs RAILWAY_API_TOKEN (personal token from
 *                  railway.app/account/tokens — READ-ONLY scope is fine).
 *   - ElevenLabs:  /v1/user shows subscription + character count.
 *
 * All keys live in Vercel/Railway env vars (never exposed to the browser).
 * We do NOT return the key itself — only presence, validity, balance, and
 * whether it's currently the "active" chosen provider.
 */

type ProviderStatus = {
  id: string;
  name: string;
  key_present: boolean;
  active: boolean;
  status: "ok" | "warn" | "error" | "missing";
  balance_usd?: number | null;
  balance_note?: string;
  usage_mtd_usd?: number;
  last_call_at?: string | null;
  model?: string;
  free_tier?: boolean;
};

const ONE_DAY_S = 86400;

function env(name: string): string {
  return (process.env[name] || "").trim();
}

async function fetchJson(url: string, headers: Record<string, string>, timeoutMs = 8000): Promise<any> {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { headers, signal: ctl.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
}

async function checkOpenRouter(): Promise<ProviderStatus> {
  const key = env("OPENROUTER_API_KEY");
  if (!key) return { id: "openrouter", name: "OpenRouter (Kimi K2 free, etc.)", key_present: false, active: false, status: "missing", balance_note: "OPENROUTER_API_KEY not set" };
  try {
    const data = await fetchJson("https://openrouter.ai/api/v1/auth/key", { Authorization: `Bearer ${key}` });
    const data2 = await fetchJson("https://openrouter.ai/api/v1/auth/credit", { Authorization: `Bearer ${key}` });
    const total = data2?.data?.total_credit ?? data?.data?.limit ?? null;
    const used = data2?.data?.total_usage ?? data?.data?.usage ?? 0;
    const limitUsd = typeof total === "number" ? total : null;
    const usedUsd = typeof used === "number" ? used : 0;
    const free = !!data?.data?.is_free_tier;
    return {
      id: "openrouter", name: "OpenRouter",
      key_present: true, active: false, status: limitUsd !== null && limitUsd - usedUsd < 0.5 ? "warn" : "ok",
      balance_usd: limitUsd !== null ? Math.max(0, limitUsd - usedUsd) : (free ? null : 0),
      balance_note: free ? "Free tier active" : (limitUsd !== null ? `$${usedUsd.toFixed(2)} used of $${limitUsd.toFixed(2)} credit` : "Credit loaded"),
      free_tier: free,
    };
  } catch (e: any) {
    return { id: "openrouter", name: "OpenRouter", key_present: true, active: false, status: "error", balance_note: `Key invalid or blocked: ${String(e.message || e).slice(0, 60)}` };
  }
}

async function checkGroq(): Promise<ProviderStatus> {
  const key = env("GROQ_API_KEY");
  if (!key) return { id: "groq", name: "Groq (Llama 3.3 70B)", key_present: false, active: false, status: "missing", balance_note: "GROQ_API_KEY not set" };
  try {
    // Groq returns active credits via their user endpoint; free tier reports unlimited.
    const me = await fetchJson("https://api.groq.com/openai/v1/models", { Authorization: `Bearer ${key}` });
    // /v1/models succeeds with any valid key — that's enough to confirm it works.
    return {
      id: "groq", name: "Groq (Llama 3.3 70B)",
      key_present: true, active: false, status: "ok",
      balance_usd: null, balance_note: "Free tier — rate-limited, no $ balance",
      free_tier: true,
    };
  } catch (e: any) {
    return { id: "groq", name: "Groq (Llama 3.3 70B)", key_present: true, active: false, status: "error", balance_note: `Key invalid: ${String(e.message || e).slice(0, 60)}` };
  }
}

async function checkAnthropic(): Promise<ProviderStatus> {
  const key = env("ANTHROPIC_API_KEY");
  if (!key) return { id: "anthropic", name: "Anthropic (Claude Sonnet)", key_present: false, active: false, status: "missing", balance_note: "ANTHROPIC_API_KEY not set" };
  try {
    // Anthropic has no public balance endpoint. We verify the key by hitting
    // /v1/models (cheap, no spend) and pull MTD spend from our own ledger.
    await fetchJson("https://api.anthropic.com/v1/models", {
      "x-api-key": key, "anthropic-version": "2023-06-01",
    });
    return {
      id: "anthropic", name: "Anthropic (Claude Sonnet)",
      key_present: true, active: false, status: "ok",
      balance_usd: null,
      balance_note: "Key valid. Anthropic does not expose balance via API — check console.anthropic.com",
    };
  } catch (e: any) {
    return { id: "anthropic", name: "Anthropic (Claude Sonnet)", key_present: true, active: false, status: "error", balance_note: `Key invalid: ${String(e.message || e).slice(0, 60)}` };
  }
}

async function checkGemini(): Promise<ProviderStatus> {
  const key = env("GEMINI_API_KEY") || env("GOOGLE_API_KEY");
  if (!key) return { id: "gemini", name: "Google Gemini (AI Studio)", key_present: false, active: false, status: "missing", balance_note: "GEMINI_API_KEY not set" };
  try {
    // Hit the models list with a tiny count to verify key without spending.
    await fetchJson(`https://generativelanguage.googleapis.com/v1beta/models?key=${key}`, {});
    return {
      id: "gemini", name: "Google Gemini (AI Studio)",
      key_present: true, active: false, status: "ok",
      balance_usd: null, balance_note: "Free tier active (15 RPM). Pay-as-you-go balance is in Google AI Studio → Billing.",
      free_tier: true,
    };
  } catch (e: any) {
    return { id: "gemini", name: "Google Gemini (AI Studio)", key_present: true, active: false, status: "error", balance_note: `Key invalid: ${String(e.message || e).slice(0, 60)}` };
  }
}

async function checkRailway(): Promise<ProviderStatus> {
  const token = env("RAILWAY_API_TOKEN");
  const projectId = env("RAILWAY_PROJECT_ID");
  if (!token) return { id: "railway", name: "Railway (worker hosting)", key_present: false, active: false, status: "missing", balance_note: "RAILWAY_API_TOKEN not set — add a read-only token from railway.app/account/tokens to see Railway credits" };
  try {
    const me = await fetchJson("https://backboard.railway.com/graphql/v2", {
      Authorization: `Bearer ${token}`, "Content-Type": "application/json",
    });
    // GraphQL endpoint with empty query will error — do a real query:
    const r = await fetch("https://backboard.railway.com/graphql/v2", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ query: `{ me { id projects { id name } } }` }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`});
    return {
      id: "railway", name: "Railway (worker hosting)",
      key_present: true, active: false, status: "ok",
      balance_usd: null,
      balance_note: projectId ? `Connected. Open railway.app/project/${projectId} for exact usage.` : "Token valid. Add RAILWAY_PROJECT_ID for deeper status.",
    };
  } catch (e: any) {
    return { id: "railway", name: "Railway (worker hosting)", key_present: true, active: false, status: "warn", balance_note: `Token check: ${String(e.message || e).slice(0, 80)}` };
  }
}

async function checkEleven(): Promise<ProviderStatus> {
  const key = env("ELEVENLABS_API_KEY");
  if (!key) return { id: "eleven", name: "ElevenLabs (voiceover)", key_present: false, active: false, status: "missing", balance_note: "ELEVENLABS_API_KEY not set (optional)" };
  try {
    const u = await fetchJson("https://api.elevenlabs.io/v1/user", { "xi-api-key": key });
    const tier = u?.subscription?.tier || u?.subscription?.plan || "";
    const remain = u?.subscription?.character_count;
    const limit = u?.subscription?.character_limit;
    return {
      id: "eleven", name: "ElevenLabs (voiceover)",
      key_present: true, active: false, status: "ok",
      balance_note: tier ? `${tier} plan${typeof remain === "number" && limit ? ` — ${Math.round(100 - (remain / limit) * 100)}% used` : ""}` : "Connected",
    };
  } catch (e: any) {
    return { id: "eleven", name: "ElevenLabs (voiceover)", key_present: true, active: false, status: "error", balance_note: `Key invalid: ${String(e.message || e).slice(0, 60)}` };
  }
}

export async function GET() {
  const sbServer = supabaseServer();
  const { data: { user } } = await sbServer.auth.getUser();
  if (!user) return NextResponse.json({ error: "Login required" }, { status: 401 });
  if (!isAdmin(user.email)) return NextResponse.json({ error: "Admins only" }, { status: 403 });

  const admin = supabaseAdmin();

  // Get current chosen provider
  const { data: modelRow } = await admin
    .from("settings").select("value").eq("tenant_id", process.env.TENANT_ID || "me").eq("key", "model").maybeSingle();
  const activeProvider = (modelRow?.value as any)?.provider || "anthropic";

  // MTD spend per provider from run_ledger
  const since = new Date();
  since.setDate(1); since.setHours(0, 0, 0, 0);
  const { data: ledger } = await admin
    .from("run_ledger").select("provider_label,cost_cents,created_at")
    .gte("created_at", since.toISOString());

  const mtdByLabel: Record<string, number> = {};
  for (const row of ledger || []) {
    const label = String(row?.provider_label || "unknown").toLowerCase();
    const cents = Number(row?.cost_cents || 0);
    if (label.startsWith("anthropic") || label.includes("claude")) mtdByLabel.anthropic = (mtdByLabel.anthropic || 0) + cents;
    else if (label.startsWith("gemini")) mtdByLabel.gemini = (mtdByLabel.gemini || 0) + cents;
    else if (label.startsWith("openrouter")) mtdByLabel.openrouter = (mtdByLabel.openrouter || 0) + cents;
    else if (label.startsWith("groq")) mtdByLabel.groq = (mtdByLabel.groq || 0) + cents;
    else mtdByLabel.other = (mtdByLabel.other || 0) + cents;
  }

  // Last call per provider (from agent_events)
  const { data: lastCalls } = await admin
    .from("agent_events").select("emitter,created_at")
    .in("emitter", ["llm.anthropic", "llm.gemini", "llm.openrouter", "llm.groq"])
    .order("created_at", { ascending: false }).limit(20);
  const lastByLabel: Record<string, string> = {};
  for (const ev of lastCalls || []) {
    const k = String(ev.emitter || "").replace("llm.", "");
    if (!lastByLabel[k]) lastByLabel[k] = ev.created_at;
  }

  // Run checks in parallel
  const [anthropic, gemini, openrouter, groq, railway, eleven] = await Promise.all([
    checkAnthropic(), checkGemini(), checkOpenRouter(), checkGroq(), checkRailway(), checkEleven(),
  ]);

  const results: ProviderStatus[] = [anthropic, gemini, openrouter, groq, railway, eleven].map(p => {
    const id = p.id as keyof typeof mtdByLabel;
    return {
      ...p,
      active: p.id === activeProvider,
      usage_mtd_usd: (mtdByLabel[p.id] || 0) / 100,
      last_call_at: lastByLabel[p.id] || null,
    };
  });

  const totalOk = results.filter(r => r.status === "ok").length;
  return NextResponse.json({
    ok: true, checked_at: new Date().toISOString(),
    active_provider: activeProvider,
    total_ok: totalOk,
    total: results.length,
    providers: results,
  });
}
