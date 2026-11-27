-- One-time setup of the AI service's database area in the EXISTING Supabase project.
-- Run it once in the Supabase SQL Editor (as the default postgres user), after enabling
-- the "vector" extension (Database > Extensions). Replace the password placeholder first.
--
-- What it creates:
--   ppa_ai_app : the login the AI service uses. It owns the "ai" schema, so the service can
--                apply its own migrations on every deploy (start.sh), exactly like Flask does
--                with "flask db upgrade". It has NO access to Flask's tables in "public".
--   ai         : the schema for the AI tables (knowledge base, usage, audit log). Supabase's
--                Data API exposes only "public" by default, so "ai" is not reachable through it.
--
-- Safe to read before running: it grants nothing on "public" and changes no existing table.

-- 1. The login. Use a long random password and keep it only in Render's settings.
CREATE ROLE ppa_ai_app LOGIN PASSWORD '<PASTE-A-LONG-RANDOM-PASSWORD>';

-- 2. The schema, owned by that login (so migrations can create and alter its tables).
--    On PostgreSQL 16+ the creator must be a member of a role to give it a schema.
GRANT ppa_ai_app TO postgres;
CREATE SCHEMA IF NOT EXISTS ai AUTHORIZATION ppa_ai_app;

-- 3. pgvector lives in Supabase's "extensions" schema: allow using the vector type there.
GRANT USAGE ON SCHEMA extensions TO ppa_ai_app;
ALTER ROLE ppa_ai_app SET search_path = ai, extensions;

-- 4. Keep it out of everything else in this database.
REVOKE ALL ON SCHEMA public FROM ppa_ai_app;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM ppa_ai_app;
ALTER ROLE ppa_ai_app SET statement_timeout = '30s';

-- 5. Check (should return: ppa_ai_app | t | f):
--    SELECT r.rolname, has_schema_privilege(r.rolname, 'ai', 'CREATE'),
--           has_table_privilege(r.rolname, 'public.user', 'SELECT')
--    FROM pg_roles r WHERE r.rolname = 'ppa_ai_app';
