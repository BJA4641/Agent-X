"""captions.py — word-by-word captions (MrBeast / Devin Jatho style).
Given a narration audio and the text, returns a list of (word, start_s, end_s)
timings + burns the styled subtitle frames as transparent PNG overlays per beat.

Pipeline:
  1) edge-tts gives us word timings for free (WordBoundary events).
  2) We split words into "chunks" of 1-3 words max (kinetic, readable).
  3) We render each chunk as a 1080x1920 PNG with big bold white text,
     thick black outline, drop shadow, and a yellow highlight on the
     "power word" — the longest/most emotional word of the chunk.
  4) Return an ASS subtitle file + the chunk list for ffmpeg burn-in.

Why ASS? Because ffmpeg's libass supports: per-word karaoke highlight,
outline, shadow, fade-in/out, position animation — all in one file and
it renders on the GPU, way cleaner than Pillow-burned text.
"""
import asyncio, os, re, time
from . import config, ledger

VOICE = config.get("EDGE_VOICE", "en-US-ChristopherNeural")

# Words that get the yellow highlight treatment
POWER_WORDS = {
    # attention
    "stop", "wait", "look", "never", "always", "secret", "hidden", "free",
    "instantly", "immediately", "actually", "literally", "exactly",
    # money / results
    "money", "paid", "save", "makes", "earn", "profit", "income", "rich",
    "fast", "easy", "simple", "instant",
    # emotional
    "crazy", "insane", "wild", "shocking", "brutal", "honest", "weird",
    "dangerous", "illegal", "banned",
    # numbers / claims
    "seconds", "minutes", "hours", "days", "%", "percent", "$", "dollars",
    "10x", "100x", "1000x", "million", "billion",
    # ai-specific
    "ai", "gpt", "claude", "gemini", "chatgpt", "agent", "agents",
}


async def _timed_words(text: str, voice: str) -> list:
    """Use edge-tts to get WordBoundary events (free, no extra cost)."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    words = []
    offset = 0.0
    async for chunk in communicate.stream():
        if chunk["type"] == "WordBoundary":
            # edge-tts gives offset/duration in 100-nanosecond units
            start = chunk["offset"] / 10_000_000
            dur   = chunk["duration"] / 10_000_000
            word  = chunk["text"].strip()
            if word:
                words.append({"word": word, "start": start, "end": start + dur})
        elif chunk["type"] == "audio.end":
            pass
    return words


def timed_words(text: str, out_audio_path: str, item_id=None) -> list:
    """Generate the narration mp3 AND return word timings in one pass."""
    if config.HAS_ELEVEN:
        # ElevenLabs doesn't give free word timings; fall back to edge-tts for timings
        # then mix/replace voice later. For simplicity, use edge-tts when we need timings.
        pass
    try:
        # Save audio via edge-tts AND get timings
        import edge_tts
        async def run():
            com = edge_tts.Communicate(text, VOICE, rate="+5%")
            await com.save(out_audio_path)
        asyncio.run(run())
        words = asyncio.run(_timed_words(text, VOICE))
        if words:
            ledger.record("voice", model="edge-tts-timed", cost_usd=0, item_id=item_id)
            return words
    except Exception as e:
        ledger.record("voice", model="edge-tts-timed", ok=False, detail=str(e)[:200], item_id=item_id)
    return []


def chunk_words(words: list, max_words: int = 3, max_chars: int = 22) -> list:
    """Split word list into display chunks of ~1-3 words, broken on natural pauses.
    Returns list of chunks: {words:[...], start, end, power_idx}."""
    if not words:
        return []
    chunks = []
    cur = []
    cur_chars = 0
    for w in words:
        wlen = len(w["word"])
        if cur and (len(cur) >= max_words or cur_chars + wlen > max_chars):
            chunks.append(_finalize(cur))
            cur = []
            cur_chars = 0
        cur.append(w)
        cur_chars += wlen + 1
        # natural break on punctuation
        if w["word"].endswith((".", "!", "?", ",", ":", ";")):
            chunks.append(_finalize(cur))
            cur = []
            cur_chars = 0
    if cur:
        chunks.append(_finalize(cur))
    return chunks


def _finalize(word_list: list) -> dict:
    text_joined = " ".join(w["word"] for w in word_list)
    power_idx = 0
    best = -1
    for i, w in enumerate(word_list):
        key = re.sub(r"[^a-z0-9$%]", "", w["word"].lower())
        score = len(w["word"])  # longer = more likely the payload
        if key in POWER_WORDS:
            score += 100
        if w["word"].startswith(("$", "£", "€")) or w["word"].endswith(("%", "x")):
            score += 50
        if score > best:
            best = score
            power_idx = i
    return {
        "words": word_list,
        "text": text_joined,
        "start": word_list[0]["start"],
        "end":   word_list[-1]["end"],
        "power_idx": power_idx,
    }


def write_ass(chunks: list, out_path: str, total_dur: float,
              video_w: int = 1080, video_h: int = 1920) -> str:
    """Write an ASS subtitle file with pop-in animation, bold font, thick
    outline, drop shadow, yellow power-word. ffmpeg burns this in with
    -vf ass=file.ass for perfectly sharp text."""
    font = "DejaVu Sans Bold"
    # Position: lower third — 200px from bottom, centered
    margin_v = 280
    # ASS has 0,0 top-left; playres determines virtual coords. We use 1080x1920.
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_w}",
        f"PlayResY: {video_h}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # Main style: white fill, 8px black outline, soft shadow
        f"Style: Main,{font},110,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,8,4,2,80,80,{margin_v},1",
        # Power word: yellow fill, black outline
        f"Style: Power,{font},120,&H0000FFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,120,120,0,0,1,9,5,2,80,80,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def ass_time(s):
        h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
        return f"{h:d}:{m:02d}:{sec:05.2f}"

    for c in chunks:
        start = max(0, c["start"] - 0.02)
        end   = min(total_dur, c["end"] + 0.15)
        # Pop-in effect: \fad(80,100) = 80ms fade in, 100ms fade out
        # \t(0,120,\fscx120\fscy120) = scale pop
        parts = []
        for i, w in enumerate(c["words"]):
            style = "Power" if i == c["power_idx"] else "Main"
            # The \r tag resets to the named style inside a line
            prefix = r"{\r" + style + r"\t(0,80,\fscx115\fscy115)\t(80,180,\fscx100\fscy100)}" if i == 0 else r"{\r" + style + "}"
            # per-word stagger: each word appears ~50ms after prior
            parts.append(prefix + w["word"])
        text = " ".join(parts)
        # Add gentle pop at start of chunk
        fx = r"{\an2\fad(60,80)}" + text
        lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Main,,0,0,0,,{fx}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
