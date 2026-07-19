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
# This is the #1 fix for the "cannot import name 'memory'" crash: old .py files
# from a previous deploy were sitting in /app/agent/ and masking new ones.
RUN rm -rf /app/* /app/.* 2>/dev/null || true

COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy prompts first (rarely change) then pipeline code.
COPY prompts/ ../prompts/
COPY pipeline/ .

# Smoke-test imports BEFORE starting the loop. If any agent module fails to
# import, the DOCKER BUILD ITSELF FAILS with a clear message showing the exact
# module + traceback, instead of Railway restart-looping with a cryptic cascade.
RUN python boot_check.py

# Creative engine tick every 60 seconds. Idle ticks are cheap; real work
# (LLM + render) is gated by DAILY_BUDGET_USD and the empty-queue check.
# Set KILL_SWITCH=1 to pause everything.
CMD ["python", "cli.py", "loop", "--interval", "60"]
