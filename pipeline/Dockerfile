# Pipeline worker — deploy to Railway. Needs ffmpeg, so NOT Vercel.
FROM python:3.12-slim

# ffmpeg for video, fonts for rendered text (DejaVu + Noto for broader Unicode + emoji)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg \
      fonts-dejavu-core \
      fonts-noto-color-emoji \
      fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Wipe any stale files from previous layer state FIRST, then install python deps.
RUN rm -rf /app/* /app/.* 2>/dev/null || true

COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy prompts first (rarely change) then pipeline code.
COPY prompts/ ../prompts/
COPY pipeline/ .

# Smoke-test imports BEFORE starting the loop.
RUN python boot_check.py

# v5 — run the blueprint-backed event-driven worker (single process, single
# active account, hard budget cap). The legacy `cli.py loop` is still
# available via `python cli.py loop` if you need to revert.
CMD ["python", "cli.py", "worker"]
