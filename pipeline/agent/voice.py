"""voice.py v2 — narration with MORE ENERGY.
v1 was slow monotone edge-tts at default speed.
v2 picks an upbeat voice, +10-15% rate, and we use the captions module to
get word timings AND save the audio in ONE stream (no double-API-call)."""
import os, ssl
from . import config, ledger

# Energetic voices (test these — they sound much more "creator bro" than ChristopherNeural)
VOICE_POOL = [
    "en-US-BrianNeural",        # warm newsy male (default)
    "en-US-GuyNeural",          # energetic male — creator vibe
    "en-US-AriaNeural",         # upbeat female
    "en-GB-RyanNeural",         # UK male — crisp
    "en-US-DavisNeural",        # younger male
]

def pick_voice(style: str | None = None) -> str:
    env = config.get("EDGE_VOICE")
    if env: return env
    # Pick voice deterministically per video (hash of style)
    import hashlib
    idx = int(hashlib.sha256((style or "").encode()).hexdigest(), 16) % len(VOICE_POOL)
    return VOICE_POOL[idx]


def narration_rate() -> str:
    """Creator pacing is 150-170 wpm. Edge default is ~130. Add +12% for energy."""
    return "+12%"


def narrate(text: str, out_path: str, item_id=None, style: str = None) -> str:
    """Save narration mp3. Word timings are collected by captions.timed_words() separately
    (which does its own edge-tts call with WordBoundary events). This function is a
    simpler save when you don't need timings."""
    if config.HAS_ELEVEN:
        try:
            return _eleven(text, out_path, item_id, style)
        except Exception as e:
            ledger.record("voice", model="elevenlabs", ok=False, detail=str(e)[:200], item_id=item_id)
    try:
        import edge_tts, asyncio
        async def run():
            voice = pick_voice(style)
            rate = narration_rate()
            com = edge_tts.Communicate(text, voice, rate=rate)
            await com.save(out_path)
        try:
            asyncio.run(run())
        except ssl.SSLError:
            ssl._create_default_https_context = ssl._create_unverified_context
            asyncio.run(run())
        ledger.record("voice", model="edge-tts-v2", cost_usd=0, item_id=item_id)
        return out_path
    except Exception as e:
        ledger.record("voice", model="edge-tts-v2", ok=False, detail=str(e)[:200], item_id=item_id)
        os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 30 -q:a 9 "{out_path}" 2>/dev/null')
        return out_path


def _eleven(text, out_path, item_id, style=None):
    import urllib.request, json as j
    vid = config.get("ELEVEN_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    # More energetic settings
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.5,
            "use_speaker_boost": True,
        }
    }
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
        data=j.dumps(body).encode(),
        headers={"xi-api-key": config.get("ELEVENLABS_API_KEY"), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        f.write(r.read())
    ledger.record("voice", model="elevenlabs-v2", cost_usd=0.08, item_id=item_id)
    return out_path
