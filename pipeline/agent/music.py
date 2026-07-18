"""music.py — background bed under the voiceover.
Priority: real tracks in MUSIC_DIR (royalty-free mp3/wav you drop in) -> synth ambient bed (MUSIC_SYNTH=1, default) -> none.
Track choice is deterministic per item id, so re-renders are idempotent."""
import os, glob, hashlib, subprocess
from . import config

MOODS = {
    "calm":  "0.20*sin(2*PI*220*t)+0.16*sin(2*PI*277.18*t)+0.14*sin(2*PI*329.63*t)",   # A minor pad
    "focus": "0.20*sin(2*PI*196*t)+0.16*sin(2*PI*246.94*t)+0.14*sin(2*PI*293.66*t)",   # G major pad
    "drive": "0.22*sin(2*PI*146.83*t)*(0.75+0.25*sin(2*PI*2*t))+0.14*sin(2*PI*220*t)", # D pulse
}

def _stable(item_id) -> int:
    return int(hashlib.sha256(str(item_id).encode()).hexdigest(), 16)

def for_item(item_id, seconds: float, workdir: str):
    """Return a music file path for this item, or None."""
    mdir = config.get("MUSIC_DIR") or "assets/music"
    tracks = sorted(sum((glob.glob(os.path.join(mdir, e)) for e in ("*.mp3", "*.wav", "*.m4a")), []))
    if tracks:
        return tracks[_stable(item_id) % len(tracks)]
    if config.get("MUSIC_SYNTH", "1") != "1":
        return None
    mood = list(MOODS)[_stable(item_id) % len(MOODS)]
    out = os.path.join(workdir, f"bed-{mood}.wav")
    if not os.path.exists(out):
        expr = MOODS[mood]
        af = ("aeval=" + expr.replace(",", "\\,") + ",")
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"aevalsrc={expr}:s=44100:d={max(seconds,8):.1f}",
               "-af", "lowpass=f=900,tremolo=f=0.15:d=0.35,volume=0.9", out]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except Exception:
            return None
    return out
