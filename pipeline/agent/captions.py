"""captions.py v4.1.1 — word-by-word captions (MrBeast / Devin Jatho style).
SINGLE edge-tts call to both save audio AND collect WordBoundary timings
(no more double-call race condition that was corrupting audio files).
"""
import asyncio, os, re
from . import config, ledger

VOICE = config.get("EDGE_VOICE", "en-US-BrianNeural")
RATE  = "+12%"  # match voice.py upbeat rate

POWER_WORDS = {
    "stop","wait","look","never","always","secret","hidden","free","instantly",
    "immediately","actually","literally","exactly",
    "money","paid","save","makes","earn","profit","income","rich","fast","easy","simple","instant",
    "crazy","insane","wild","shocking","brutal","honest","weird","dangerous","illegal","banned",
    "seconds","minutes","hours","days","%","percent","$","dollars","10x","100x","million","billion",
    "ai","gpt","claude","gemini","chatgpt","agent","agents","delete","click","follow",
}


async def _stream_and_save(text: str, voice: str, rate: str, out_path: str) -> list:
    """One edge-tts stream: write audio to disk AND collect WordBoundary events."""
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate)
    words = []
    with open(out_path, "wb") as fh:
        async for chunk in com.stream():
            ctype = chunk["type"]
            if ctype == "audio":
                fh.write(chunk["data"])
            elif ctype == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                dur   = chunk["duration"] / 10_000_000
                word  = chunk["text"].strip()
                if word:
                    words.append({"word": word, "start": start, "end": start + dur})
    return words


def timed_words(text: str, out_audio_path: str, item_id=None, style: str = None) -> list:
    """Generate narration mp3 AND word timings in ONE pass (the only edge-tts call)."""
    # Pick voice from voice.pick_voice if possible, fall back to Christopher/default
    voice = VOICE
    try:
        from . import voice as _voice
        voice = _voice.pick_voice(style)
    except Exception:
        pass
    rate = RATE
    try:
        words = asyncio.run(_stream_and_save(text, voice, rate, out_audio_path))
        if words:
            # Sanity: audio file should exist and be non-tiny
            if os.path.exists(out_audio_path) and os.path.getsize(out_audio_path) > 500:
                ledger.record("voice", model=f"edge-tts-{voice}", cost_usd=0, item_id=item_id)
                return words
            else:
                raise RuntimeError("audio file too small")
    except Exception as e:
        ledger.record("voice", model="edge-tts", ok=False, detail=str(e)[:200], item_id=item_id)
        # Write a silent fallback so composer never crashes
        try:
            import subprocess
            subprocess.run(["ffmpeg","-y","-f","lavfi","-i","anullsrc=r=24000:cl=mono",
                            "-t","35","-q:a","9","-c:a","libmp3lame",out_audio_path],
                           capture_output=True, timeout=30)
        except Exception:
            pass
        return []
    return []


def chunk_words(words: list, max_words: int = 3, max_chars: int = 22) -> list:
    if not words: return []
    chunks = []; cur = []; cur_chars = 0
    for w in words:
        wlen = len(w["word"])
        if cur and (len(cur) >= max_words or cur_chars + wlen > max_chars):
            chunks.append(_finalize(cur)); cur = []; cur_chars = 0
        cur.append(w); cur_chars += wlen + 1
        if w["word"].endswith((".","!","?",":",";")):
            chunks.append(_finalize(cur)); cur = []; cur_chars = 0
    if cur: chunks.append(_finalize(cur))
    return chunks


def _finalize(word_list: list) -> dict:
    text_joined = " ".join(w["word"] for w in word_list)
    power_idx = 0; best = -1
    for i, w in enumerate(word_list):
        key = re.sub(r"[^a-z0-9$%]", "", w["word"].lower())
        score = len(w["word"])
        if key in POWER_WORDS: score += 100
        if w["word"].startswith(("$","£","€")) or w["word"].endswith(("%","x")): score += 50
        if score > best: best = score; power_idx = i
    return {"words": word_list, "text": text_joined,
            "start": word_list[0]["start"], "end": word_list[-1]["end"],
            "power_idx": power_idx}


def write_ass(chunks: list, out_path: str, total_dur: float,
              video_w: int = 1080, video_h: int = 1920) -> str:
    """Write an ASS subtitle file with pop-in, bold outline, yellow power word."""
    font = "DejaVu Sans Bold"
    margin_v = 280
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_w}", f"PlayResY: {video_h}",
        "ScaledBorderAndShadow: yes", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Main,{font},110,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,8,4,2,80,80,{margin_v},1",
        f"Style: Power,{font},120,&H0000FFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,120,120,0,0,1,9,5,2,80,80,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    def ass_time(s):
        s = max(0.0, float(s))
        h = int(s//3600); m = int((s%3600)//60); sec = s%60
        return f"{h:d}:{m:02d}:{sec:05.2f}"
    for c in chunks:
        start = max(0, c["start"]-0.02)
        end   = min(total_dur, c["end"]+0.15)
        parts = []
        for i, w in enumerate(c["words"]):
            style = "Power" if i == c["power_idx"] else "Main"
            pop = r"{\t(0,80,\fscx115\fscy115)\t(80,180,\fscx100\fscy100)}" if i == 0 else ""
            parts.append(r"{\r" + style + r"}" + pop + w["word"])
        text = " ".join(parts)
        fx = r"{\an2\fad(60,80)}" + text
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Main,,0,0,0,,{fx}")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
