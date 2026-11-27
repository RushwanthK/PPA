#!/bin/sh
# Start script for the AI service container (Render). Mirrors the Flask backend's start.sh:
# the database is brought up to date on every deploy, before the app starts.
#
# 1. Migrations (db/migrations/*.sql) are applied to AI_DATABASE_URL (Supabase in
#    production). Already-applied ones are skipped; a changed one stops the deploy
#    (checksum), so the service never runs against a schema it does not expect.
# 2. The help notes (knowledge/) are synced into the vector tables. Only new or changed
#    text is embedded (one Gemini call for the changes, none when nothing changed); notes
#    deleted from the repo are removed. A failure here is logged and the service starts
#    anyway with the notes already stored.
# 3. The API starts on Render's $PORT.
set -e

echo "Applying AI database migrations..."
python -m app.migrate

echo "Syncing help notes into the vector store..."
python -m app.rag.ingest || echo "Help-note sync failed; starting with the notes already stored."

echo "Starting the AI service..."
exec python -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
