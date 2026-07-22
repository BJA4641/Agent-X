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

def eleven_key() -> str:
    """v5.6: accept BOTH env spellings (docs said ELEVEN_API_KEY, code read
    ELEVENLABS_API_KEY — that mismatch silently disabled premium voice)."""
    return config.get("ELEVENLABS_API_KEY") or config.get("ELEVEN_API_KEY") or ""


# ---- v5.6 daily character cap so ElevenLabs can never eat the budget ----
_ELEVEN_DAY = {"day": None, "used": 0}

def _eleven_cap() -> int:
    try:
        return int(config.get("ELEVEN_DAILY_CHAR_CAP", "10000"))
    except Exception:
        return 10000

def eleven_chars_ok(n: int) -> bool:
    import datetime as _dt
    today = _dt.date.today().isoformat()
    if _ELEVEN_DAY["day"] != today:
        _ELEVEN_DAY["day"] = today; _ELEVEN_DAY["used"] = 0
    return (_ELEVEN_DAY["used"] + max(0, n)) <= _eleven_cap()

def eleven_chars_add(n: int):
    import datetime as _dt
    today = _dt.date.today().isoformat()
    if _ELEVEN_DAY["day"] != today:
        _ELEVEN_DAY["day"] = today; _ELEVEN_DAY["used"] = 0
    _ELEVEN_DAY["used"] += max(0, n)


def eleven_timed_words(text: str, out_audio_path: str, item_id=None, style=None) -> list:
    """v5.6: ElevenLabs narration WITH word timings in one call, using the
    /with-timestamps endpoint (character alignment -> word windows). This is
    what lets premium voice drive perfectly-synced reel captions. Raises on
    any failure so the caller can fall back to edge-tts."""
    import urllib.request, json as j, base64
    key = eleven_key()
    if not key:
        raise RuntimeError("no ElevenLabs key")
    if not eleven_chars_ok(len(text)):
        raise RuntimeError(f"eleven daily char cap reached ({_eleven_cap()})")
    vid = config.get("ELEVEN_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    body = {
        "text": text,
        "model_id": config.get("ELEVEN_MODEL_ID", "eleven_multilingual_v2"),
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.8,
                            "style": 0.5, "use_speaker_boost": True},
    }
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps",
        data=j.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = j.loads(r.read().decode())
    audio_b64 = payload.get("audio_base64")
    align = payload.get("alignment") or payload.get("normalized_alignment") or {}
    chars = align.get("characters") or []
    starts = align.get("character_start_times_seconds") or []
    ends = align.get("character_end_times_seconds") or []
    if not audio_b64 or not chars:
        raise RuntimeError("eleven timestamps response missing audio/alignment")
    with open(out_audio_path, "wb") as f:
        f.write(base64.b64decode(audio_b64))
    # Group character alignment into word timings
    words, cur, w_start, last_end = [], "", None, 0.0
    for i, ch in enumerate(chars):
        st = float(starts[i]) if i < len(starts) else last_end
        en = float(ends[i]) if i < len(ends) else st
        last_end = en
        if ch.strip() == "":
            if cur:
                words.append({"word": cur, "start": w_start or 0.0, "end": en})
                cur, w_start = "", None
        else:
            if not cur:
                w_start = st
            cur += ch
    if cur:
        words.append({"word": cur, "start": w_start or 0.0, "end": last_end})
    eleven_chars_add(len(text))
    # Cost estimate: ~$0.15 per 1k chars (starter-tier ballpark, stamped for ROI math)
    est = round(len(text) / 1000.0 * 0.15, 5)
    ledger.record("voice", model="elevenlabs-timed", cost_usd=est, item_id=item_id)
    return words


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
    if (config.HAS_ELEVEN or eleven_key()) and eleven_chars_ok(len(text)):
        try:
            out = _eleven(text, out_path, item_id, style)
            eleven_chars_add(len(text))
            return out
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
        headers={"xi-api-key": eleven_key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        f.write(r.read())
    ledger.record("voice", model="elevenlabs-v2", cost_usd=0.08, item_id=item_id)
    return out_path
