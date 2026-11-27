-- Runs once when the local AI database is first created.
-- In Supabase the same statements are applied by hand (or by a migration) later.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ai;
