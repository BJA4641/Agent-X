"""sfx.py — synthesized short sound effects for transitions (whoosh/pop/tick).
Generates short WAVs with ffmpeg on demand so you don't need to bundle audio assets.
All effects are ~0.3-0.6s and meant to be placed under a beat cut at low volume.
"""
import os, subprocess, hashlib

CACHE = {}

def _gen(name: str, expr: str, dur: float, workdir: str) -> str:
    key = name + "_" + hashlib.md5(expr.encode()).hexdigest()[:8]
    path = os.path.join(workdir, f"sfx_{key}.wav")
    if os.path.exists(path):
        return path
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
           f"aevalsrc={expr}:s=44100:d={dur}",
           "-af", "afade=t=out:st=0:d={d},highpass=f=200,lowpass=f=8000".format(d=dur),
           path]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        CACHE[name] = path
        return path
    except Exception:
        return None


def whoosh(workdir: str) -> str:
    """Band-passed noise sweeping down → classic transition whoosh."""
    expr = ("0.25*sin(2*PI*(1200-600*t/0.4)*t)"
            "+0.20*(random(0)-0.5)*exp(-3*t)")
    return _gen("whoosh", expr, 0.40, workdir)


def pop(workdir: str) -> str:
    """Short click/pop for bullet points."""
    expr = "0.6*sin(2*PI*400*t)*exp(-20*t)"
    return _gen("pop", expr, 0.12, workdir)


def tick(workdir: str) -> str:
    """Subtle tick/clack for number reveals."""
    expr = "0.4*sin(2*PI*1500*t)*exp(-30*t)"
    return _gen("tick", expr, 0.08, workdir)


def riser(workdir: str) -> str:
    """Short rising sweep for the hook → first beat transition."""
    expr = "0.20*sin(2*PI*(200+1200*t/0.5)*t)*exp(-2.5*(0.5-t))"
    return _gen("riser", expr, 0.50, workdir)


def for_cut(cut_idx: int, workdir: str) -> str | None:
    """Pick a different SFX per cut position so transitions don't feel repetitive."""
    bank = [whoosh, pop, tick, whoosh, pop, riser, whoosh, tick]
    fn = bank[cut_idx % len(bank)]
    return fn(workdir)
