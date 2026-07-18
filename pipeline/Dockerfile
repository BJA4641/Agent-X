# Pipeline worker — deploy to Railway / Render / Fly / any VPS (needs ffmpeg, so NOT Vercel).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY prompts/ ../prompts/
COPY pipeline/ .
# One tick every 30 min. Set env vars in the host dashboard; KILL_SWITCH=1 stops everything.
CMD ["python", "cli.py", "loop", "--interval", "1800"]
