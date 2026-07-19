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

# Install python deps
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy prompts first (rarely change) then pipeline code
COPY prompts/ ../prompts/
COPY pipeline/ .

# Creative engine v2 tick every 60 seconds. Idle ticks are cheap; real work
# (LLM + render) is gated by DAILY_BUDGET_USD and the empty-queue check.
# Set KILL_SWITCH=1 to pause everything.
CMD ["python", "cli.py", "loop", "--interval", "60"]
