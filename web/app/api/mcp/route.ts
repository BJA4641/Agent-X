/**
 * /api/mcp — Agent-X MCP (Model Context Protocol) endpoint.
 *
 * Lets users connect Claude Desktop / ChatGPT / Cursor / any MCP-compatible
 * client directly to their Agent-X account so they can chat with Claude and
 * say things like "queue a Reel on X" or "show me my agent feed" — Claude
 * calls this endpoint and the work gets done on Agent-X.
 *
 * Auth: bearer token issued from Settings → MCP (stored in mcp_connections).
 * Transport: HTTP+JSON (Streamable HTTP variant, simplest to host on Vercel).
 *
 * Tools exposed:
 *   - agentx_queue_topic    { topic: string, project?: string }
 *   - agentx_list_feed      { limit?: number }
 *   - agentx_list_drafts    {}
 *   - agentx_approve_draft  { item_id: string }
 *   - agentx_reject_draft   { item_id: string, reason?: string }
 *   - agentx_wallet_status  {}
 *   - agentx_projects_list  {}
 *   - agentx_kill_switch    { on: boolean }
 *   - agentx_trends         { niche?: string, limit?: number }
 *   - agentx_diagnostics    {}   health, ladder, escalation, spend in one call
 *   - agentx_failures       { limit?, agent? }   full untruncated errors
 *   - agentx_agent_chatter  { limit?, agent?, action?, since_minutes? }
 *   - agentx_pipeline_state {}   board + job counts, queued by type
 *   - agentx_account_control{ handle, action?, daily_budget_usd?, posts_per_day? }
 *   - agentx_budget_control { daily_budget_usd?, account_monthly_cap_usd? }
 *   - agentx_retry_failed   { job_type?, limit? }
 *
 * NOTE: names use UNDERSCORES. Claude validates remote tool names against
 * ^[a-zA-Z0-9_-]{1,64}$ — a dot rejects the ENTIRE conversation (v5.11.2).
 *
 * This endpoint is intentionally permissive (CORS * on POST) so MCP clients
 * work; but every action is scoped to the user who owns the token.
 */
import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase/server";
import crypto from "crypto";

export const dynamic = "force-dynamic";
export const maxDuration = 30;

type JsonRpcId = string | number | null;
type JsonRpcReq = { jsonrpc: "2.0"; id?: JsonRpcId; method: string; params?: any };
type JsonRpcRes = { jsonrpc: "2.0"; id: JsonRpcId; result?: any; error?: { code: number; message: string; data?: any } };

const JSONRPC_PARSE_ERROR = -32700;
const JSONRPC_INVALID_REQ = -32600;
const JSONRPC_METHOD_NOT_FOUND = -32601;
const JSONRPC_INVALID_PARAMS = -32602;
const JSONRPC_INTERNAL = -32603;

function reply(id: JsonRpcId, result: any): NextResponse {
  return NextResponse.json({ jsonrpc: "2.0", id, result });
}
function fail(id: JsonRpcId, code: number, message: string, data?: any): NextResponse {
  return NextResponse.json({ jsonrpc: "2.0", id, error: { code, message, data } }, { status: code === -32600 ? 400 : code === -32601 ? 404 : 200 });
}
function errRes(id: JsonRpcId, e: any): NextResponse {
  return fail(id, JSONRPC_INTERNAL, String(e?.message || e));
}

// ---------- auth ----------
async function authenticate(req: Request): Promise<{ user_id: string } | null> {
  const h = req.headers.get("authorization") || "";
  const m = h.match(/^Bearer\s+(.+)$/i);
  if (!m) return null;
  const token = m[1].trim();
  if (!token) return null;
  // v5.10.6 REQ-MCP-OAUTH: two accepted credential types.
  //  1. axat_… — OAuth access token (what Claude.ai connectors obtain)
  //  2. axmcp_… — legacy personal token from Settings → MCP (Cursor, scripts)
  if (token.startsWith("axat_")) {
    const { data: t } = await supabaseAdmin()
      .from("oauth_tokens")
      .select("user_id,expires_at,revoked_at")
      .eq("access_token", token)
      .maybeSingle();
    if (!t?.user_id) return null;
    if ((t as any).revoked_at) return null;
    if (new Date((t as any).expires_at).getTime() < Date.now()) return null;
    return { user_id: (t as any).user_id };
  }
  const { data } = await supabaseAdmin()
    .from("mcp_connections")
    .select("user_id")
    .eq("access_token", token)
    .is("revoked_at", null)
    .maybeSingle();
  if (!data?.user_id) return null;
  // Touch last_used_at (best-effort)
  supabaseAdmin().from("mcp_connections")
    .update({ last_used_at: new Date().toISOString() })
    .eq("access_token", token)
    .then(()=>{}, ()=>{});
  return { user_id: data.user_id };
}

// ---------- MCP manifest: initialize / tools/list ----------
const SERVER_INFO = { name: "agent-x", version: "0.1.0" };
const CAPABILITIES = { tools: {} };

function buildToolsList() {
  return {
    tools: [
      {
        name: "agentx_queue_topic",
        description: "Queue a new topic for the Agent-X content crew. They will script, shoot, edit and hand a draft back for your approval. Use this whenever the user wants a new Reel/TikTok/Short made.",
        inputSchema: {
          type: "object",
          properties: {
            topic: { type: "string", description: "One sentence describing the content, e.g. 'A Reel on why Claude Projects beats ChatGPT memory'" },
            project: { type: "string", description: "Optional project/niche name (defaults to your active project)" }
          },
          required: ["topic"]
        }
      },
      {
        name: "agentx_list_feed",
        description: "Show the latest agent activity feed — what your agents are working on right now (last N events).",
        inputSchema: {
          type: "object",
          properties: { limit: { type: "number", default: 20, maximum: 100 } }
        }
      },
      {
        name: "agentx_list_drafts",
        description: "List content drafts that are waiting for your approval (status=drafted). Approve or reject each from here.",
        inputSchema: { type: "object", properties: {} }
      },
      {
        name: "agentx_approve_draft",
        description: "Approve a drafted item so it gets scheduled and published. Pass the item_id (from list_drafts).",
        inputSchema: {
          type: "object",
          properties: { item_id: { type: "string", description: "The board item id (UUID or short prefix)" } },
          required: ["item_id"]
        }
      },
      {
        name: "agentx_reject_draft",
        description: "Reject a drafted item. Agents won't publish it; optionally give a reason so they learn.",
        inputSchema: {
          type: "object",
          properties: {
            item_id: { type: "string" },
            reason: { type: "string", description: "Why rejected — becomes standing editor feedback." }
          },
          required: ["item_id"]
        }
      },
      {
        name: "agentx_wallet_status",
        description: "Check your current wallet balance and total spent.",
        inputSchema: { type: "object", properties: {} }
      },
      {
        name: "agentx_projects_list",
        description: "List your active projects / niches.",
        inputSchema: { type: "object", properties: {} }
      },
      {
        name: "agentx_kill_switch",
        description: "Pause (true) or resume (false) ALL agents immediately.",
        inputSchema: {
          type: "object",
          properties: { on: { type: "boolean", description: "true = paused, false = running" } },
          required: ["on"]
        }
      },
      {
        name: "agentx_account_control",
        description: "Pause or resume a single account, or set its daily budget / posts-per-day. Founder-approved write access (v5.10.7). Always report what changed.",
        inputSchema: { type: "object", properties: {
          handle: { type: "string", description: "account handle, e.g. puppy.parent" },
          action: { type: "string", enum: ["pause", "resume", "status"] },
          daily_budget_usd: { type: "number" },
          posts_per_day: { type: "number" } }, required: ["handle"] },
      },
      {
        name: "agentx_budget_control",
        description: "Read or set the global daily budget and per-account monthly cap. Setting a budget is deliberate spend authorisation — echo the old and new values back.",
        inputSchema: { type: "object", properties: {
          daily_budget_usd: { type: "number" },
          account_monthly_cap_usd: { type: "number" } } },
      },
      {
        name: "agentx_retry_failed",
        description: "Requeue failed or stuck jobs so they run again immediately (clears backoff). Optionally filter by job_type.",
        inputSchema: { type: "object", properties: {
          job_type: { type: "string" }, limit: { type: "number" } } },
      },
      {
        name: "agentx_diagnostics",
        description: "One-shot health snapshot: worker version + heartbeat age, free-model ladder (usable/dropped rungs), last escalation verdict, cost per published post, and today's spend. Use this FIRST when something looks wrong.",
        inputSchema: { type: "object", properties: {} },
      },
      {
        name: "agentx_failures",
        description: "Recent failures with FULL error text: failed jobs and error/critical agent events. Use to find which agent broke and why.",
        inputSchema: { type: "object", properties: {
          limit: { type: "number", description: "max rows per category (default 15)" },
          agent: { type: "string", description: "optional: filter events to one agent, e.g. brain, cqo, cfo" } } },
      },
      {
        name: "agentx_agent_chatter",
        description: "The agent conversation log, optionally filtered by agent or action. This is what the agents 'say' to each other as they work.",
        inputSchema: { type: "object", properties: {
          limit: { type: "number" }, agent: { type: "string" },
          action: { type: "string" }, since_minutes: { type: "number" } } },
      },
      {
        name: "agentx_pipeline_state",
        description: "Where every board item and job currently sits — counts by status, plus what is queued and in flight. Answers 'why is nothing publishing'.",
        inputSchema: { type: "object", properties: {} },
      },
      {
        name: "agentx_trends",
        description: "Browse currently-trending content ideas across the web for your niche.",
        inputSchema: {
          type: "object",
          properties: {
            niche: { type: "string", description: "Niche slug (e.g. ai_tools, finance)" },
            limit: { type: "number", default: 10, maximum: 30 }
          }
        }
      },
      {
        name: "agentx_railway_status",
        description: "Live Railway status for the Python worker: services, latest deployment state (SUCCESS/FAILED/CRASHED/BUILDING) and deploy time. Use when the heartbeat banner looks wrong or after pushing a new build.",
        inputSchema: { type: "object", properties: {} }
      },
      {
        name: "agentx_railway_logs",
        description: "Tail the Railway worker's logs (build + runtime). Omit deployment_id to read the latest deployment. This is how you see crash tracebacks without opening the Railway dashboard.",
        inputSchema: {
          type: "object",
          properties: {
            deployment_id: { type: "string", description: "Optional — from agentx_railway_status; defaults to the latest deployment" },
            limit: { type: "number", default: 80, maximum: 400 }
          }
        }
      }
    ]
  };
}

// ---------- Railway (v5.11.23 REQ-RAILWAY-MCP, DEC-076) ----------
// A production-scoped Railway project token (env RAILWAY_PROJECT_TOKEN, set in
// Vercel) lets the assistant read deploy status + logs directly instead of
// asking the founder for dashboard screenshots. Read-only queries only —
// restarts/redeploys stay a human action on purpose.
const RAILWAY_GQL = "https://backboard.railway.com/graphql/v2";
async function railwayGQL(query: string, variables: Record<string, any>) {
  const token = process.env.RAILWAY_PROJECT_TOKEN || "";
  if (!token) throw new Error("RAILWAY_PROJECT_TOKEN is not set in Vercel env — add it (Production scope) and redeploy.");
  const r = await fetch(RAILWAY_GQL, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Project-Access-Token": token },
    body: JSON.stringify({ query, variables }),
    // Railway GraphQL can be slow on cold logs — cap it so MCP doesn't hang.
    signal: AbortSignal.timeout(15000),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.errors?.length)
    throw new Error("Railway API: " + (j.errors?.[0]?.message || `HTTP ${r.status}`));
  return j.data;
}
async function railwayLatestDeployments() {
  // A project token is already scoped to one project+environment, so the
  // deployments query needs no ids — ask for the newest few, newest first.
  const d = await railwayGQL(
    `query { deployments(first: 8) { edges { node {
        id status createdAt staticUrl
        service { name }
      } } } }`, {});
  return (d?.deployments?.edges || []).map((e: any) => e.node);
}

// ---------- tool handlers ----------
async function runTool(name: string, params: any, userId: string) {
  // v5.11.2 REQ-MCP-TOOLNAMES: Claude validates tool names against
  // ^[a-zA-Z0-9_-]{1,64}$ — dots are NOT allowed. Every tool here shipped as
  // "agentx.foo", so the connector authorised, loaded the tool list, and then
  // the whole conversation was rejected with:
  //   tools.305.FrontendRemoteMcpToolDefinition.name: String should match ...
  // Canonical names are now "agentx_foo". Existing Desktop/Cursor configs that
  // still send the dotted form keep working via this normalisation.
  name = String(name || "").replace(/^agentx\./, "agentx_");

  const sb = supabaseAdmin();
  const TENANT = process.env.TENANT_ID || "me";

  if (name === "agentx_queue_topic") {
    const topic = String(params?.topic || "").trim();
    if (!topic) throw new Error("topic is required");
    const { data, error } = await sb.from("board_items").insert({
      tenant_id: TENANT, status: "idea",
      topic: topic.slice(0, 200),
      payload: { bucket: "user", source: "mcp", queued_by: userId }
    }).select("id,topic,status").single();
    if (error) throw error;
    await sb.from("agent_events").insert({
      tenant_id: TENANT, user_id: userId, agent: "system", action: "mcp_queue",
      message: "Queued via MCP: " + topic.slice(0,120), status: "success"
    });
    return { queued: true, item: data };
  }

  if (name === "agentx_list_feed") {
    const limit = Math.min(Number(params?.limit) || 20, 100);
    const { data } = await sb.from("agent_events")
      .select("agent,action,message,status,cost_usd,created_at")
      .or(`user_id.eq.${userId},and(user_id.is.null,tenant_id.eq.${TENANT})`)
      .order("created_at", { ascending: false }).limit(limit);
    return { events: data || [] };
  }

  if (name === "agentx_list_drafts") {
    const { data } = await sb.from("board_items")
      .select("id,topic,status,created_at,payload")
      .eq("tenant_id", TENANT).eq("status", "drafted")
      .order("created_at", { ascending: false }).limit(25);
    return { drafts: (data || []).map((d: any) => ({
        id: d.id, topic: d.topic, created_at: d.created_at,
        hook: d.payload?.script?.hook,
        video_url: d.payload?.video_url || null,
        style: d.payload?.style || null,
    })) };
  }

  if (name === "agentx_approve_draft") {
    const id = await resolveItemId(sb, params?.item_id, TENANT, "drafted");
    const { error } = await sb.from("board_items").update({ status: "approved" }).eq("id", id);
    if (error) throw error;
    await sb.from("agent_events").insert({
      tenant_id: TENANT, user_id: userId, agent: "publisher", action: "mcp_approve",
      message: "Approved via MCP (id " + id.slice(0,8) + ")", status: "success"
    });
    return { approved: true, item_id: id };
  }

  if (name === "agentx_reject_draft") {
    const id = await resolveItemId(sb, params?.item_id, TENANT, "drafted");
    const reason = String(params?.reason || "Rejected via MCP.").slice(0, 400);
    const { error } = await sb.from("board_items").update({
        status: "rejected",
        payload: { rejection: { reason, at: new Date().toISOString() } }
      }).eq("id", id);
    if (error) throw error;
    await sb.from("agent_events").insert({
      tenant_id: TENANT, user_id: userId, agent: "qa", action: "mcp_reject",
      message: "Rejected via MCP: " + reason, status: "warn"
    });
    return { rejected: true, item_id: id };
  }

  if (name === "agentx_wallet_status") {
    const { data } = await sb.from("wallets").select("balance_usd,lifetime_topup,lifetime_spent")
      .eq("user_id", userId).maybeSingle();
    return { wallet: data || { balance_usd: 0, lifetime_topup: 0, lifetime_spent: 0 } };
  }

  if (name === "agentx_projects_list") {
    const { data } = await sb.from("projects")
      .select("id,name,niche,platforms,status,created_at")
      .eq("user_id", userId).eq("status", "active").order("created_at").limit(200);
    return { projects: data || [] };
  }

  if (name === "agentx_kill_switch") {
    const on = Boolean(params?.on);
    const { error } = await sb.from("settings").upsert(
      { tenant_id: TENANT, key: "kill_switch", value: { on } },
      { onConflict: "tenant_id,key" });
    if (error) throw error;
    return { kill_switch: on };
  }

  if (name === "agentx_account_control") {
    const handle = String(params?.handle || "").replace(/^@/, "");
    if (!handle) throw new Error("handle is required");
    const { data: acct } = await sb.from("project_accounts")
      .select("id,name,handle,status,paused,daily_budget_usd,posts_per_day")
      .eq("handle", handle).maybeSingle();
    if (!acct) throw new Error(`no account with handle ${handle}`);
    const before = { ...(acct as any) };
    const patch: any = {};
    if (params?.action === "pause") { patch.paused = true; patch.status = "paused"; }
    if (params?.action === "resume") { patch.paused = false; patch.status = "ready"; }
    if (typeof params?.daily_budget_usd === "number") patch.daily_budget_usd = params.daily_budget_usd;
    if (typeof params?.posts_per_day === "number") patch.posts_per_day = params.posts_per_day;
    if (Object.keys(patch).length === 0) return { account: before, changed: false };
    const { error } = await sb.from("project_accounts").update(patch).eq("id", (acct as any).id);
    if (error) throw error;
    await sb.from("agent_events").insert({
      tenant_id: TENANT, agent: "human_desk", status: "info", action: "mcp_account_control",
      message: `account ${handle} updated via MCP: ${JSON.stringify(patch)}`,
    });
    return { account: handle, before, changed: patch };
  }

  if (name === "agentx_budget_control") {
    const out: any = {};
    const readKey = async (k: string) => {
      const { data } = await sb.from("settings").select("value").eq("tenant_id", TENANT)
        .eq("key", k).maybeSingle();
      return (data as any)?.value ?? null;
    };
    out.before = { daily_budget: await readKey("daily_budget"),
                   account_monthly_budget: await readKey("account_monthly_budget") };
    const writes: any = {};
    if (typeof params?.daily_budget_usd === "number") {
      await sb.from("settings").upsert(
        { tenant_id: TENANT, key: "daily_budget", value: { usd: params.daily_budget_usd } },
        { onConflict: "tenant_id,key" });
      writes.daily_budget = params.daily_budget_usd;
    }
    if (typeof params?.account_monthly_cap_usd === "number") {
      await sb.from("settings").upsert(
        { tenant_id: TENANT, key: "account_monthly_budget",
          value: { usd: params.account_monthly_cap_usd, note: "set via MCP" } },
        { onConflict: "tenant_id,key" });
      writes.account_monthly_cap = params.account_monthly_cap_usd;
    }
    out.changed = writes;
    out.after = { daily_budget: await readKey("daily_budget"),
                  account_monthly_budget: await readKey("account_monthly_budget") };
    return out;
  }

  if (name === "agentx_retry_failed") {
    const limit = Math.min(Number(params?.limit) || 20, 100);
    let q = sb.from("jobs").select("id,job_type,status")
      .in("status", ["failed", "queued"]).limit(limit);
    if (params?.job_type) q = q.eq("job_type", String(params.job_type));
    const { data: rows } = await q;
    const ids = (rows || []).map((r: any) => r.id);
    if (ids.length === 0) return { requeued: 0 };
    const { error } = await sb.from("jobs")
      .update({ status: "queued", scheduled_for: Math.floor(Date.now() / 1000),
                claimed_at: null, error: "requeued via MCP" })
      .in("id", ids);
    if (error) throw error;
    return { requeued: ids.length, job_types: [...new Set((rows || []).map((r: any) => r.job_type))] };
  }

  if (name === "agentx_diagnostics") {
    const out: any = {};
    const { data: wh } = await sb.from("worker_health").select("*").limit(50);
    out.workers = (wh || []).map((r: any) => ({
      id: r.worker_id, version: r.version, host: r.host,
      heartbeat_age_s: Math.round(Date.now() / 1000 - Number(r.last_heartbeat_at || 0)),
      jobs_completed: r.jobs_completed, jobs_failed: r.jobs_failed,
    }));
    const { data: st } = await sb.from("settings").select("key,value").limit(300)
      .in("key", ["free_ladder_report", "escalation_last", "heartbeat_pulse",
                  "cost_per_post", "kill_switch", "cost_mode", "sla_status"]);
    for (const row of st || []) out[(row as any).key] = (row as any).value;
    const startOfDay = new Date(); startOfDay.setUTCHours(0, 0, 0, 0);
    const { data: led } = await sb.from("run_ledger").select("cost_usd,model").limit(5000)
      .gte("created_at", startOfDay.toISOString());
    const rows = led || [];
    out.spend_today_usd = Number(rows.reduce((a: number, r: any) => a + Number(r.cost_usd || 0), 0).toFixed(4));
    const byModel: Record<string, number> = {};
    for (const r of rows) byModel[(r as any).model || "?"] = (byModel[(r as any).model || "?"] || 0) + Number((r as any).cost_usd || 0);
    out.spend_by_model = byModel;
    return out;
  }

  if (name === "agentx_failures") {
    const limit = Math.min(Number(params?.limit) || 15, 50);
    const jobsQ = sb.from("jobs").select("job_type,error,attempts,created_at")
      .eq("status", "failed").order("created_at", { ascending: false }).limit(limit);
    const { data: failedJobs } = await jobsQ;
    let evQ = sb.from("agent_events").select("agent,action,status,message,created_at")
      .in("status", ["error", "critical", "warn"])
      .order("created_at", { ascending: false }).limit(limit);
    if (params?.agent) evQ = evQ.eq("agent", String(params.agent));
    const { data: errEvents } = await evQ;
    return {
      failed_jobs: (failedJobs || []).map((j: any) => ({
        job_type: j.job_type, attempts: j.attempts, at: j.created_at,
        error: String(j.error || ""),          // FULL text, deliberately untruncated
      })),
      error_events: (errEvents || []).map((e: any) => ({
        agent: e.agent, action: e.action, status: e.status,
        at: e.created_at, message: String(e.message || ""),
      })),
    };
  }

  if (name === "agentx_agent_chatter") {
    const limit = Math.min(Number(params?.limit) || 50, 200);
    let q = sb.from("agent_events").select("agent,action,status,message,created_at,item_id,job_id")
      .order("created_at", { ascending: false }).limit(limit);
    if (params?.agent) q = q.eq("agent", String(params.agent));
    if (params?.action) q = q.eq("action", String(params.action));
    if (params?.since_minutes) {
      const since = new Date(Date.now() - Number(params.since_minutes) * 60000).toISOString();
      q = q.gte("created_at", since);
    }
    const { data } = await q;
    return { count: (data || []).length, events: data || [] };
  }

  if (name === "agentx_pipeline_state") {
    /* v5.11.19 REQ-MCP-EXACT-COUNTS — these numbers were silently wrong.
     *
     * The previous implementation did `select("status")` and counted the rows
     * that came back. PostgREST caps a request at 1000 rows by default, so
     * EVERY count saturated at exactly 1000. Verified against the database on
     * 2026-07-24:
     *      board cleared   MCP 984   actual 7,402   (7.5x under)
     *      jobs done       MCP 987   actual 40,554  (41x under)
     *      jobs queued     MCP 3     actual 25
     *      jobs in_progress / claimed — absent entirely, because no such row
     *      appeared in the first 1000
     * The totals gave it away: board 984+2+1+5+3+5 = 1000, jobs 987+3+10 = 1000.
     *
     * This matters more than an internal metric. The connector is intended to be
     * the ONLY diagnostic surface for users who never touch the database, and it
     * was reporting a 40,554-job queue as 987 healthy jobs.
     *
     * Fixed with head-only exact counts (count: "exact", head: true) — no rows
     * are transferred, so this is cheaper than the broken version as well as
     * correct.
     */
    const out: any = {};

    const countWhere = async (table: string, col: string, val: string) => {
      const { count, error } = await sb.from(table)
        .select("*", { count: "exact", head: true }).eq(col, val);
      return error ? null : (count ?? 0);
    };

    const BOARD_STATUSES = ["idea", "drafted", "approved", "scheduled",
                            "published", "rejected", "failed", "cleared"];
    const JOB_STATUSES = ["queued", "claimed", "in_progress", "done", "failed"];

    const bc: Record<string, number> = {};
    await Promise.all(BOARD_STATUSES.map(async (st) => {
      const n = await countWhere("board_items", "status", st);
      if (n) bc[st] = n;
    }));
    out.board_by_status = bc;

    const jc: Record<string, number> = {};
    await Promise.all(JOB_STATUSES.map(async (st) => {
      const n = await countWhere("jobs", "status", st);
      if (n) jc[st] = n;
    }));
    out.jobs_by_status = jc;

    // Queued work is bounded and small, so listing it is safe.
    const { data: queued } = await sb.from("jobs").select("job_type")
      .eq("status", "queued").limit(500);
    const qt: Record<string, number> = {};
    for (const r of queued || []) qt[(r as any).job_type] = (qt[(r as any).job_type] || 0) + 1;
    out.queued_by_type = qt;

    /* Accounts: the old version returned all 107, of which 105 are paused —
     * thousands of tokens per call to say "paused" over and over. */
    const { data: acc } = await sb.from("project_accounts")
      .select("handle,status,paused,posts_per_day").limit(500);
    const all = acc || [];
    out.accounts_active = all.filter((a: any) => !a.paused).map((a: any) => ({
      handle: a.handle, status: a.status, posts_per_day: a.posts_per_day }));
    out.accounts_paused_count = all.filter((a: any) => a.paused).length;
    out.counts_are_exact = true;
    return out;
  }

  if (name === "agentx_trends") {
    const limit = Math.min(Number(params?.limit) || 10, 30);
    let q = sb.from("trend_items").select("niche,platform,title,url,heat,engagement,published_at")
      .eq("tenant_id", TENANT).order("heat", { ascending: false });
    if (params?.niche) q = q.eq("niche", String(params.niche));
    const { data } = await q.limit(limit);
    return { trends: data || [] };
  }

  if (name === "agentx_railway_status") {
    const deps = await railwayLatestDeployments();
    return {
      deployments: deps.map((n: any) => ({
        id: n.id, service: n.service?.name || "?", status: n.status,
        created_at: n.createdAt, url: n.staticUrl || null,
      })),
      hint: "status BUILDING/DEPLOYING = push in progress; CRASHED/FAILED = read agentx_railway_logs",
    };
  }

  if (name === "agentx_railway_logs") {
    const limit = Math.min(Number(params?.limit) || 80, 400);
    let depId = String(params?.deployment_id || "").trim();
    if (!depId) {
      const deps = await railwayLatestDeployments();
      if (!deps.length) throw new Error("No deployments visible to this token.");
      depId = deps[0].id;
    }
    const d = await railwayGQL(
      `query($id: String!, $limit: Int!) {
         deploymentLogs(deploymentId: $id, limit: $limit) {
           timestamp severity message
         }
       }`, { id: depId, limit });
    const logs = (d?.deploymentLogs || []).map((l: any) =>
      `${l.timestamp} [${l.severity}] ${l.message}`);
    return { deployment_id: depId, lines: logs.length, logs };
  }

  throw new Error("Unknown tool: " + name);
}

async function resolveItemId(sb: any, prefix: any, tenant: string, mustBeStatus?: string): Promise<string> {
  const p = String(prefix || "").trim();
  if (!p) throw new Error("item_id is required");
  let q = sb.from("board_items").select("id,status").eq("tenant_id", tenant);
  if (p.length >= 36) q = q.eq("id", p);
  else q = q.like("id", p + "%");
  const { data, error } = await q.limit(2);
  if (error) throw error;
  if (!data || data.length === 0) throw new Error("No item found for id " + p);
  if (data.length > 1) throw new Error("Ambiguous id prefix — paste more characters.");
  if (mustBeStatus && data[0].status !== mustBeStatus)
    throw new Error("Item is status='" + data[0].status + "', expected '" + mustBeStatus + "'");
  return data[0].id;
}

// ---------- HTTP handlers ----------
async function handle(req: Request): Promise<NextResponse> {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new NextResponse(null, { status: 204, headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
      "Access-Control-Max-Age": "86400"
    }});
  }
  if (req.method !== "POST" && req.method !== "GET") {
    return NextResponse.json({ error: "method not allowed" }, { status: 405 });
  }

  // Initialization / discovery endpoints can be unauthenticated (per MCP spec)
  const url = new URL(req.url);
  if (req.method === "GET" || url.searchParams.has("discover")) {
    return NextResponse.json({
      server: SERVER_INFO,
      capabilities: CAPABILITIES,
      auth: "bearer (issue a token from Settings → MCP)",
      tools: buildToolsList().tools
    }, { headers: { "Access-Control-Allow-Origin": "*" }});
  }

  let body: any;
  try { body = await req.json(); }
  catch { return fail(null, JSONRPC_PARSE_ERROR, "Parse error"); }

  // Support batch arrays (optional MCP feature)
  if (Array.isArray(body)) {
    const out = [];
    for (const r of body) out.push(await handleSingle(r, req));
    return NextResponse.json(out, { headers: { "Access-Control-Allow-Origin": "*" }});
  }
  const res = await handleSingle(body, req);
  return NextResponse.json(res, { headers: { "Access-Control-Allow-Origin": "*" }});
}

async function handleSingle(body: JsonRpcReq, req: Request): Promise<JsonRpcRes> {
  const id = body?.id ?? null;
  if (!body || body.jsonrpc !== "2.0" || !body.method) {
    return { jsonrpc: "2.0", id, error: { code: JSONRPC_INVALID_REQ, message: "Invalid JSON-RPC request" } };
  }

  // MCP lifecycle: initialize
  if (body.method === "initialize") {
    return { jsonrpc: "2.0", id, result: {
      protocolVersion: "2024-11-05", serverInfo: SERVER_INFO, capabilities: CAPABILITIES
    }};
  }
  if (body.method === "notifications/initialized" || body.method?.startsWith("notifications/")) {
    return { jsonrpc: "2.0", id: null, result: {} };  // no response needed

  }
  if (body.method === "ping") {
    return { jsonrpc: "2.0", id, result: { pong: true, ts: Date.now() } };
  }
  if (body.method === "tools/list") {
    return { jsonrpc: "2.0", id, result: buildToolsList() };
  }

  // All tool calls require a valid bearer token
  const auth = await authenticate(req);
  if (!auth) {
    // v5.10.6: point unauthenticated clients at the OAuth discovery document so
    // Claude's connector can start the registration flow instead of guessing.
    return { jsonrpc: "2.0", id, error: { code: -32001,
      message: "Unauthorized. Connect via OAuth (see /.well-known/oauth-protected-resource) "
             + "or supply a personal token from Settings → MCP.",
      data: { www_authenticate: "Bearer resource_metadata=\"/.well-known/oauth-protected-resource\"" } } };
  }

  if (body.method === "tools/call") {
    const name = body.params?.name;
    const args = body.params?.arguments || {};
    try {
      const result = await runTool(name, args, auth.user_id);
      return { jsonrpc: "2.0", id, result: { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] } };
    } catch (e: any) {
      return { jsonrpc: "2.0", id, error: { code: JSONRPC_INTERNAL, message: String(e?.message || e) } };
    }
  }

  return { jsonrpc: "2.0", id, error: { code: JSONRPC_METHOD_NOT_FOUND, message: "Unknown method: " + body.method } };
}

// v5.11.3: `export { handle }` was here and BROKE EVERY VERCEL BUILD.
// A Next.js route.ts may only export GET/HEAD/POST/PUT/DELETE/PATCH/OPTIONS and
// the config keys (dynamic, revalidate, runtime, maxDuration, ...). Any other
// named export fails type validation at build time, so four deployments errored
// in a row and the tool-name fix never reached production — which is why the
// connector kept rejecting the conversation with a name that was already fixed
// in the repo. If the catch-all is ever wanted, move the handler into
// web/lib/mcp/handler.ts and import it from both routes.
export { handle as GET, handle as POST, handle as OPTIONS };
