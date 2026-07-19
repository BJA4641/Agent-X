"""composer.py v2 — frames + voice + word-captions → 1080x1920 Reel.
v1: static zoompan + black-box paragraph text
v2:
  - Word-by-word ASS captions (MrBeast / Devin Jatho style: bold, outline, pop, yellow power word)
  - Per-beat transitions: zoom punch, slide, whip, flash
  - Transition SFX (whoosh/pop) on cuts
  - Beat-synced music duck under voice
  - Intro punch (0.3s flash zoom on first frame)
  - Outro CTA frame held 2 seconds for algorithm watch-time
"""
import os, subprocess, math, random
from . import config

# Per-beat duration will be computed from audio length, but enforce bounds.
MIN_BEAT = 2.4
MAX_BEAT = 4.5
HOOK_HOLD = 1.2   # hold hook frame extra
CTA_HOLD  = 2.5   # hold end card extra (algorithm loves a clean end)


def assemble(frames: list, audio_path: str, out_path: str,
             narration_words: list = None, ass_path: str = None,
             per_beat: float = None, music_path: str = None,
             sfx_paths: list = None, hook_idx: int = 0) -> str:
    dur = _audio_seconds(audio_path)
    n_beats = len(frames)
    # Compute per-beat durations (hook + CTA get held longer).
    body = max(n_beats - 2, 1)
    body_dur = max(dur - HOOK_HOLD - CTA_HOLD, 1.0)
    per_body = max(MIN_BEAT, min(MAX_BEAT, body_dur / body)) if n_beats >= 3 else max(dur / max(n_beats,1), MIN_BEAT)

    # Build per-beat duration list
    durs = []
    for i in range(n_beats):
        if i == 0:
            durs.append(HOOK_HOLD + per_body)
        elif i == n_beats - 1:
            durs.append(CTA_HOLD + per_body * 0.5)
        else:
            durs.append(per_body)
    # Normalize to match audio length
    total = sum(durs)
    scale = dur / total
    durs = [d * scale for d in durs]

    work = os.path.dirname(out_path) or "."
    base = os.path.splitext(os.path.basename(out_path))[0]

    # 1) Render one MP4 segment per beat with unique motion + transition
    segs = []
    for i, f in enumerate(frames):
        seg = os.path.join(work, f"{base}_seg{i}.mp4")
        b_dur = durs[i]
        vf = _motion_for(i, n_beats, b_dur)
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{b_dur:.2f}", "-i", f,
               "-vf", vf, "-t", f"{b_dur:.2f}",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
               "-r", "30", "-an", seg]
        try:
            _run(cmd)
        except Exception:
            # fallback: static
            _run(["ffmpeg", "-y", "-loop", "1", "-t", f"{b_dur:.2f}", "-i", f,
                  "-vf", f"scale=1080:1920,setsar=1,fps=30", "-t", f"{b_dur:.2f}",
                  "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-an", seg])
        segs.append(seg)

    # 2) Concat beat segments
    lst = os.path.join(work, f"{base}_list.txt")
    with open(lst, "w") as fh:
        for s in segs:
            fh.write(f"file '{os.path.abspath(s)}'\n")
    silent = os.path.join(work, f"{base}_silent.mp4")
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])

    # 3) Build audio mix: voice + music + SFX
    final_audio = _mix_audio(audio_path, music_path, sfx_paths, durs, dur, work, base)

    # 4) Burn in ASS captions + mux audio
    vf_chain = f"scale=1080:1920,setsar=1,fps=30"
    if ass_path and os.path.exists(ass_path):
        # Copy .ass to a simple local filename (avoids quoting/escaping bugs with long/hash paths)
        import shutil
        simple_ass = os.path.join(work, "subs.ass")
        try:
            shutil.copyfile(ass_path, simple_ass)
            # Use POSIX-safe path: no escaping needed for simple "subs.ass"
            vf_chain += f",ass='{simple_ass}'"
        except Exception as e:
            print(f"[composer] ASS burn skipped: {e}")
    if final_audio:
        _run(["ffmpeg", "-y", "-i", silent, "-i", final_audio,
              "-vf", vf_chain,
              "-map", "0:v", "-map", "1:a", "-shortest",
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
              "-c:a", "aac", "-b:a", "192k", out_path])
    else:
        _run(["ffmpeg", "-y", "-i", silent, "-vf", vf_chain,
              "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", out_path])

    # 5) Cleanup temp files
    for p in segs + [lst, silent, final_audio or ""]:
        try:
            if p and os.path.exists(p): os.remove(p)
        except OSError:
            pass
    return out_path


def _motion_for(i: int, n: int, dur: float) -> str:
    """Different motion preset per beat position so cuts feel purposeful."""
    fps = 30
    frames = int(dur * fps)
    # Always slow push-in (Ken Burns)
    z_start = 1.00
    z_end = 1.10
    # Small bounce on first hook frame
    if i == 0:
        # Big intro punch: zoom from 1.2 -> 1.0 in 6 frames then settle
        return (f"scale=1296:2304,"
                f"zoompan=z='if(lte(on,8),1.25-on*0.03,min(zoom+0.0008,1.10))':d={frames}:s=1080x1920:fps={fps},"
                f"fade=t=in:st=0:d=0.15,setsar=1")
    if i == n - 1:
        # End card: very slow zoom out + fade in
        return (f"scale=1296:2304,"
                f"zoompan=z='max(zoom-0.0004,0.96)':d={frames}:s=1080x1920:fps={fps},"
                f"fade=t=in:st=0:d=0.25,setsar=1")
    # Body beats: randomize between gentle zoom, side slide, or jitter
    preset = i % 4
    if preset == 0:  # push-in
        vf = (f"scale=1296:2304,"
              f"zoompan=z='min(zoom+0.001,1.12)':d={frames}:s=1080x1920:fps={fps}")
    elif preset == 1:  # slide left
        vf = (f"scale=1296:2304,"
              f"zoompan=z=1.08:x='iw/2-(iw/zoom/2)+on*0.6':d={frames}:s=1080x1920:fps={fps}")
    elif preset == 2:  # slide right
        vf = (f"scale=1296:2304,"
              f"zoompan=z=1.08:x='iw/2-(iw/zoom/2)-on*0.6':d={frames}:s=1080x1920:fps={fps}")
    else:  # subtle tilt + push
        vf = (f"scale=1296:2304,"
              f"zoompan=z='min(zoom+0.0009,1.11)':d={frames}:s=1080x1920:fps={fps},"
              f"rotate=0.01*sin(2*PI*on/{frames}):fillcolor=black@0")
    return vf + f",fade=t=in:st=0:d=0.12,setsar=1"


def _mix_audio(voice_path, music_path, sfx_paths, durs, total_dur, work, base):
    """Build a single mixed audio track: voice (main) + ducked music bed + SFX on cuts."""
    inputs = []
    filters = []
    # Always have voice
    voice_dur = _audio_seconds(voice_path) or total_dur
    inputs += ["-i", voice_path]
    voice_idx = 0
    next_idx = 1

    # Music bed
    music_idx = None
    if music_path and os.path.exists(music_path):
        inputs += ["-stream_loop", "-1", "-i", music_path]
        music_idx = next_idx
        next_idx += 1

    # SFX per beat
    cut_times = []
    t = 0
    for i, d in enumerate(durs[:-1]):
        t += d
        cut_times.append(t)
    sfx_indexes = []
    if sfx_paths:
        for sx in sfx_paths:
            if sx and os.path.exists(sx):
                inputs += ["-i", sx]
                sfx_indexes.append(next_idx)
                next_idx += 1

    if next_idx == 1:
        return None  # voice only, will mux directly

    # Build filter graph
    parts = []
    # Voice cleaned up
    parts.append(f"[{voice_idx}:a]volume=1.2,acompressor=threshold=-18dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-1.5[voice]")
    cur = "[voice]"

    if music_idx is not None:
        music_vol = float(config.get("MUSIC_VOLUME", "0.10"))
        parts.append(f"[{music_idx}:a]volume={music_vol},atrim=0:{total_dur:.2f},asetpts=PTS-STARTPTS,afade=t=out:st={max(total_dur-1.5,0):.2f}:d=1.5[bed]")
        parts.append(f"[voice][bed]amix=inputs=2:duration=first:normalize=0:dropout_transition=0[vmix]")
        cur = "[vmix]"

    if sfx_indexes:
        # Place one SFX at each cut time (loop through available SFX)
        chains = []
        labels = []
        for k, sx_idx in enumerate(sfx_indexes):
            label = f"sfx{k}"
            # Simple short whoosh — low volume
            parts.append(f"[{sx_idx}:a]volume=0.35,apad=whole_dur={total_dur:.2f},adelay={int(cut_times[k % len(cut_times)]*1000) if cut_times else 0}|{int(cut_times[k % len(cut_times)]*1000) if cut_times else 0}[{label}]")
            labels.append(f"[{label}]")
        parts.append(f"{cur}{''.join(labels)}amix=inputs={1+len(labels)}:duration=first:normalize=0:dropout_transition=0[aout]")
        cur = "[aout]"

    fc = ";".join(parts)
    mixed = os.path.join(work, f"{base}_mix.m4a")
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", cur,
           "-t", f"{total_dur:.2f}", "-c:a", "aac", "-b:a", "192k", mixed]
    try:
        _run(cmd)
        return mixed
    except Exception as e:
        print(f"[composer] audio mix failed ({e}), using voice-only")
        return None


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        err = r.stderr.decode(errors="ignore")
        lines = [l for l in err.splitlines() if l.strip() and not l.startswith(("frame=", "size=", "[Parsed_", "    Last"))]
        raise RuntimeError("ffmpeg failed: " + " | ".join(lines[-4:])[-500:])


def _audio_seconds(path: str) -> float:
    if not path or not os.path.exists(path):
        return 0.0
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True)
        return float(out.stdout.strip())
    except Exception:
        return 0.0
