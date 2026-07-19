# Pipeline worker — deploy to Railway / Render / Fly / any VPS (needs ffmpeg, so NOT Vercel).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY prompts/ ../prompts/
COPY pipeline/ .
# One tick every 60 seconds. Idle ticks are cheap (1 DB read + a tiny idle-chat insert).
# Real content work (LLM + render) is gated by DAILY_BUDGET_USD and the empty-queue check,
# so a fast loop DOES NOT mean fast spending. Set KILL_SWITCH=1 to pause everything.
CMD ["python", "cli.py", "loop", "--interval", "60"]
