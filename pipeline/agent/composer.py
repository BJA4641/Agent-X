"""composer.py — frames + voiceover -> 1080x1920 mp4 with Ken Burns motion."""
import os, subprocess
from . import config

def assemble(frames: list, audio_path: str, out_path: str, per_beat: float = None, music_path: str = None) -> str:
    dur = _audio_seconds(audio_path)
    per = per_beat or max(2.5, dur / max(len(frames), 1))
    parts, inputs = [], []
    for i, f in enumerate(frames):
        inputs += ["-loop", "1", "-t", f"{per:.2f}", "-i", f]
        parts.append(
            f"[{i}:v]scale=1296:2304,zoompan=z='min(zoom+0.0012,1.12)':d={int(per*30)}:s=1080x1920:fps=30,"
            f"fade=t=in:st=0:d=0.3,setsar=1[v{i}]")
    concat = "".join(f"[v{i}]" for i in range(len(frames)))
    fc = ";".join(parts) + f";{concat}concat=n={len(frames)}:v=1:a=0[v]"
    n = len(frames)
    if music_path:
        vol = float(__import__("os").environ.get("MUSIC_VOLUME", "0.12"))
        fc += (f";[{n}:a]volume=1.0[voice];"
               f"[{n+1}:a]volume={vol},afade=t=out:st={max(dur-1.5,0):.2f}:d=1.5[bed];"
               f"[voice][bed]amix=inputs=2:duration=first:normalize=0[a]")
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_path, "-stream_loop", "-1", "-i", music_path,
               "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-c:a", "aac", out_path]
    else:
        cmd = ["ffmpeg", "-y", *inputs, "-i", audio_path, "-filter_complex", fc,
               "-map", "[v]", "-map", f"{n}:a", "-shortest",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               "-c:a", "aac", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path

def _audio_seconds(path: str) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True)
        return float(out.stdout.strip())
    except Exception:
        return 30.0
