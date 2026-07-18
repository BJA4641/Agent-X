"""composer.py — frames + voiceover -> 1080x1920 mp4 with Ken Burns motion.
v1.3: renders one beat segment at a time (low peak RAM — survives small containers),
then concats losslessly and muxes audio. Music mix failure degrades to voice-only.
"""
import os, subprocess
from . import config

def assemble(frames: list, audio_path: str, out_path: str, per_beat: float = None, music_path: str = None) -> str:
    dur = _audio_seconds(audio_path)
    per = per_beat or max(2.5, dur / max(len(frames), 1))
    work = os.path.dirname(out_path) or "."
    base = os.path.splitext(os.path.basename(out_path))[0]

    # 1) one small ffmpeg run per beat — peak memory stays flat regardless of beat count
    segs = []
    for i, f in enumerate(frames):
        seg = os.path.join(work, f"{base}_seg{i}.mp4")
        vf = (f"scale=1296:2304,zoompan=z='min(zoom+0.0012,1.12)':d={int(per*30)}:s=1080x1920:fps=30,"
              f"fade=t=in:st=0:d=0.3,setsar=1")
        _run(["ffmpeg", "-y", "-loop", "1", "-t", f"{per:.2f}", "-i", f,
              "-vf", vf, "-t", f"{per:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-an", seg])
        segs.append(seg)

    # 2) lossless concat
    lst = os.path.join(work, f"{base}_list.txt")
    with open(lst, "w") as fh:
        for s in segs:
            fh.write(f"file '{os.path.abspath(s)}'\n")
    silent = os.path.join(work, f"{base}_silent.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])

    # 3) mux audio; music bed is best-effort — never allowed to sink the video
    if music_path:
        try:
            vol = float(os.environ.get("MUSIC_VOLUME", "0.12"))
            fc = (f"[1:a]volume=1.0[voice];[2:a]volume={vol},afade=t=out:st={max(dur-1.5,0):.2f}:d=1.5[bed];"
                  f"[voice][bed]amix=inputs=2:duration=first:normalize=0[a]")
            _run(["ffmpeg", "-y", "-i", silent, "-i", audio_path, "-stream_loop", "-1", "-i", music_path,
                  "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-t", f"{dur:.2f}",
                  "-c:v", "copy", "-c:a", "aac", out_path])
        except Exception:
            music_path = None  # fall through to voice-only
    if not music_path:
        _run(["ffmpeg", "-y", "-i", silent, "-i", audio_path, "-map", "0:v", "-map", "1:a", "-shortest",
              "-c:v", "copy", "-c:a", "aac", out_path])

    for p in segs + [lst, silent]:
        try: os.remove(p)
        except OSError: pass
    return out_path

def _run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.decode()[-400:]}")

def _audio_seconds(path: str) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True)
        return float(out.stdout.strip())
    except Exception:
        return 30.0
