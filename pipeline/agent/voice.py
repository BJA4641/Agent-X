"""voice.py — narration. ElevenLabs (live) > edge-tts (free) > silent track."""
import asyncio, os, ssl
from . import config, ledger

VOICE = config.get("EDGE_VOICE", "en-US-ChristopherNeural")

def narrate(text: str, out_path: str, item_id=None) -> str:
    if config.HAS_ELEVEN:
        try:
            return _eleven(text, out_path, item_id)
        except Exception as e:
            ledger.record("voice", model="elevenlabs", ok=False, detail=str(e), item_id=item_id)
    try:
        import edge_tts
        async def run():
            await edge_tts.Communicate(text, VOICE).save(out_path)
        try:
            asyncio.run(run())
        except ssl.SSLError:
            ssl._create_default_https_context = ssl._create_unverified_context
            asyncio.run(run())
        ledger.record("voice", model="edge-tts", cost_usd=0, item_id=item_id)
        return out_path
    except Exception as e:
        ledger.record("voice", model="edge-tts", ok=False, detail=str(e), item_id=item_id)
        os.system(f'ffmpeg -y -f lavfi -i anullsrc=r=24000:cl=mono -t 30 -q:a 9 "{out_path}" 2>/dev/null')
        return out_path

def _eleven(text, out_path, item_id):
    import urllib.request, json as j
    vid = config.get("ELEVEN_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
        data=j.dumps({"text": text, "model_id": "eleven_multilingual_v2"}).encode(),
        headers={"xi-api-key": config.get("ELEVENLABS_API_KEY"), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        f.write(r.read())
    ledger.record("voice", model="elevenlabs", cost_usd=0.05, item_id=item_id)
    return out_path
