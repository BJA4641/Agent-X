-- v5.10.6 — OAuth 2.1 for the Agent-X MCP server (REQ-MCP-OAUTH)
-- Claude.ai custom connectors do not accept static bearer headers; they perform
-- Dynamic Client Registration (RFC 7591) then an authorization-code + PKCE flow.
-- These three tables are the minimum needed to serve that correctly.

create table if not exists oauth_clients (
  client_id text primary key,
  client_secret text,                       -- null => public client (PKCE only)
  client_name text,
  redirect_uris text[] not null default '{}',
  grant_types text[] not null default '{authorization_code,refresh_token}',
  token_endpoint_auth_method text not null default 'none',
  created_at timestamptz not null default now()
);
alter table oauth_clients enable row level security;

create table if not exists oauth_codes (
  code text primary key,
  client_id text not null,
  user_id uuid not null,
  redirect_uri text not null,
  code_challenge text,                      -- PKCE S256
  code_challenge_method text default 'S256',
  scope text default 'mcp',
  expires_at timestamptz not null,
  used_at timestamptz,
  created_at timestamptz not null default now()
);
alter table oauth_codes enable row level security;
create index if not exists oauth_codes_expiry on oauth_codes (expires_at);

create table if not exists oauth_tokens (
  access_token text primary key,
  refresh_token text unique,
  client_id text not null,
  user_id uuid not null,
  scope text default 'mcp',
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
alter table oauth_tokens enable row level security;
create index if not exists oauth_tokens_refresh on oauth_tokens (refresh_token);
create index if not exists oauth_tokens_user on oauth_tokens (user_id);

-- Housekeeping: expired codes are useless and must not accumulate.
-- (Run manually or from a cron job; kept as a comment so no scheduler is assumed.)
-- delete from oauth_codes where expires_at < now() - interval '1 day';
