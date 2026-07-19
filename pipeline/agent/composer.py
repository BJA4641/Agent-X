\"""composer.py — frames + voiceover -> 9:16 mp4 with Ken Burns motion.
v1.5: OOM-aware. On small containers (Railway trial = 512 MB) the kernel
kills ffmpeg mid-encode (SIGKILL, no error text). We now:
  1) detect the -9 kill and say so in the error message,
  2) automatically retry the segment at 720x1280 / ultrafast / 1 thread
     (~83 MB peak vs ~223 MB at 1080p — measured), so renders survive
     512 MB containers. Output is still 9:16 vertical; platforms upscale fine.
Set FORCE_720=1 to always render 720x1280 (fastest + cheapest), or
FORCE_1080=1 to never downshift (only on big containers).
"""
import os, subprocess
from . import config

FORCE_720 = os.environ.get("FORCE_720") == "1"
FORCE_1080 = os.environ.get("FORCE_1080") == "1"


def assemble(frames: list, audio_path: str, out_path: str, per_beat: float = None, music_path: str = None) -> str:
    dur = _audio_seconds(audio_path)
    per = per_beat or max(2.5, dur / max(len(frames), 1))
    work = os.path.dirname(out_path) or "."
    base = os.path.splitext(os.path.basename(out_path))[0]

    # 1) one small ffmpeg run per beat — peak memory stays flat regardless of beat count
    segs = []
    for i, f in enumerate(frames):
        seg = os.path.join(work, f"{base}_seg{i}.mp4")
        _encode_segment(f, seg, per)
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


def _encode_segment(frame: str, seg: str, per: float):
    """Encode one beat. Ladder: 1080 Ken Burns -> 1080 static -> 720 Ken Burns
    -> 720 static. Any OOM kill (SIGKILL) just drops us to the next rung."""
    d = int(per * 30)
    hi_motion = ([f"scale=1296:2304,zoompan=z='min(zoom+0.0012,1.12)':d={d}:s=1080x1920:fps=30,"
                  f"fade=t=in:st=0:d=0.3,setsar=1"], "veryfast", None)
    hi_static = (["scale=1080:1920,setsar=1,fps=30"], "veryfast", None)
    lo_motion = ([f"scale=864:1536,zoompan=z='min(zoom+0.0012,1.12)':d={d}:s=720x1280:fps=30,"
                  f"fade=t=in:st=0:d=0.3,setsar=1"], "ultrafast", "1")
    lo_static = (["scale=720:1280,setsar=1,fps=30"], "ultrafast", "1")

    if FORCE_720:
        ladder = [lo_motion, lo_static]
    elif FORCE_1080:
        ladder = [hi_motion, hi_static]
    else:
        ladder = [hi_motion, hi_static, lo_motion, lo_static]

    last_err = None
    for vf, preset, threads in ladder:
        cmd = ["ffmpeg", "-y"]
        if threads:
            cmd += ["-threads", threads]
        cmd += ["-loop", "1", "-t", f"{per:.2f}", "-i", frame, "-vf", vf[0], "-t", f"{per:.2f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", preset, "-an", seg]
        try:
            _run(cmd)
            return
        except Exception as e:
            last_err = e
    raise last_err


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err = r.stderr.decode(errors="ignore")
        lines = [l for l in err.splitlines() if l.strip() and not l.startswith(("frame=", "size="))]
        tail = " | ".join(lines[-6:])[-400:]
        if r.returncode in (-9, 137):
            tail = "KILLED BY OS (exit %s — out of memory on this container). " % r.returncode + tail
        raise RuntimeError("ffmpeg failed (exit %s): " % r.returncode + tail)


def _audio_seconds(path: str) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True)
        return float(out.stdout.strip())
    except Exception:
        return 30.0
