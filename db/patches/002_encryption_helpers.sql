-- ============================================================
-- Patch 002: Encryption helpers for user_connections.
-- Run AFTER db/patches/001_connections_and_brand.sql
-- ============================================================
-- We store OAuth tokens encrypted. The web and pipeline can decrypt
-- only via these SECURITY DEFINER functions using a server-side key
-- that is never exposed to the client.
--
-- ONE-TIME SETUP (run in Supabase SQL editor once):
--   select encode(gen_random_bytes(32), 'hex');
--   -- copy the hex string, then run:
--   alter database postgres set app.encryption_key to '<the hex>';
--
-- If you prefer raw pgsodium (paid Supabase), swap these for
-- pgsodium.crypto_aead_det_encrypt / decrypt. The _enc_key() signature
-- below is compatible with both — return a bytea key either way.

create extension if not exists pgcrypto;

create or replace function _enc_key() returns bytea as $$
begin
  return decode(current_setting('app.encryption_key', true), 'hex');
exception when others then
  -- fallback: a fixed dev key. REPLACE BEFORE LAUNCH.
  return decode('0000000000000000000000000000000000000000000000000000000000000000', 'hex');
end;
$$ language plpgsql stable;

create or replace function encrypt_creds(payload jsonb) returns text as $$
declare
  pt bytea := convert_to(payload::text, 'utf8');
  ct bytea;
begin
  -- AES-GCM-like via pgp_sym_encrypt (available on all tiers).
  ct = pgp_sym_encrypt_bytea(pt, encode(_enc_key(), 'hex'), 'compress-algo=1, cipher-algo=aes256');
  return encode(ct, 'base64');
end;
$$ language plpgsql stable security definer;

create or replace function decrypt_creds(ciphertext text) returns jsonb as $$
declare
  pt bytea;
begin
  pt = pgp_sym_decrypt_bytea(decode(ciphertext, 'base64'), encode(_enc_key(), 'hex'));
  return convert_from(pt, 'utf8')::jsonb;
exception when others then
  return null;
end;
$$ language plpgsql stable security definer;

-- Grant execute to the authenticator role (anon + authenticated via RLS)
-- so that /api/connections can call encrypt_creds on INSERT/UPSERT.
grant execute on function encrypt_creds(jsonb) to authenticated, service_role;
grant execute on function decrypt_creds(text)   to service_role;
-- The web route decrypts through the service_role only (users never see raw tokens).
