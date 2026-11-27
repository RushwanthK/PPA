# PPA AI service (FastAPI) for Render, built from this folder (Render "Root Directory": ai_service).
# Same pattern as the Flask backend: start.sh applies migrations, then starts the app.
# Measured (step 6, Nov 27): about 45 MB idle and 47 MB under load at 512 MB / 0.1 CPU.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Dependencies first, so code changes do not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the service needs at run time: code, migrations and the help notes.
COPY app ./app
COPY db ./db
COPY knowledge ./knowledge
COPY start.sh .
RUN chmod +x start.sh

# Run as a normal user, not root.
RUN useradd --create-home --uid 10001 ppa
USER ppa

EXPOSE 8000
CMD ["./start.sh"]
