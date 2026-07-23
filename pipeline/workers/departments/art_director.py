"""departments/art_director.py — v5.10.0 REQ-ARTDIRECTOR-1.

The gap this closes
-------------------
Until now a beat's image prompt was whatever the writer happened to put in
`beat.visual_prompt` — often a sentence of narration, not a picture brief. The
renderer then asked an image model for "3 AI skincare scanners that predict
breakouts", which is a *topic*, not a *shot*. That is the difference between
"AI made a video" and "AI directed a video", and it is the single biggest
quality gap against dedicated faceless-reel tools.

The Art Director converts each beat into a structured SHOT:
    subject · composition · lighting · camera · style · palette · negative
and composes those into the `visual_prompt` string the renderer already reads,
while keeping the structured pack in `beat.art` for future regeneration loops.

Cost + safety stance (DEC-041)
------------------------------
* ONE call per reel, not one per beat — direction is a single creative act.
* Free council first. Escalates only through the existing paid ladder, and only
  if the founder opts in via settings.art_director = {"allow_paid": true}.
* FAIL-OPEN: if the model is unavailable or returns junk, a deterministic
  template composer produces a solid prompt pack with no LLM at all. Art
  direction must never become a new reason that nothing publishes — that
  failure mode has already cost this platform its entire output history.
"""
from __future__ import annotations
import json
import os
import time
from agentcore import Worker, Job, AgentContext, Priority
from ..common import board_get, board_patch_payload, brand_context_for, job_of, load_account

ART_DIRECTOR_ENABLED = os.environ.get("ART_DIRECTOR_ENABLED", "1") != "0"
ART_MAX_BEATS = int(os.environ.get("ART_MAX_BEATS", "8"))

# Deterministic fallback vocabulary — no model required.
_COMPOSITIONS = ["centered subject, rule-of-thirds headroom",
                 "tight close-up, subject fills frame",
                 "wide establishing shot, subject small in frame",
                 "over-the-shoulder, foreground blur",
                 "flat-lay top-down, objects arranged in a grid",
                 "low angle looking up, heroic framing"]
_CAMERAS = ["85mm portrait lens, shallow depth of field",
            "35mm documentary lens, natural perspective",
            "macro lens, extreme detail",
            "24mm wide lens, slight distortion",
            "50mm prime, neutral compression"]
_LIGHTING = ["soft golden-hour window light from the left",
             "bright even studio softbox lighting",
             "moody single-source rim light against dark background",
             "diffused overcast daylight, no harsh shadows",
             "warm practical lamps, cosy interior glow"]
_NEGATIVE = ("text, watermark, logo, extra fingers, deformed hands, distorted face, "
             "blurry, low resolution, cluttered background, duplicate subject")


def register(w: Worker):
    w.register("art.direct", direct)


# --------------------------------------------------------------------- helpers

def compose_prompt(shot: dict, style_hint: str = "") -> str:
    """Turn a structured shot into the single string the renderer consumes.
    Pure function — unit-tested."""
    parts = [
        (shot.get("subject") or "").strip(),
        (shot.get("composition") or "").strip(),
        (shot.get("lighting") or "").strip(),
        (shot.get("camera") or "").strip(),
        (shot.get("style") or style_hint or "").strip(),
        (shot.get("palette") or "").strip(),
    ]
    body = ", ".join(p for p in parts if p)
    return (body + ", vertical 9:16 composition, high detail")[:900]


def fallback_pack(beats: list, topic: str, style_hint: str = "") -> list:
    """Deterministic shot list — used when no model is available. Varies
    composition/camera/lighting per beat so a reel never renders six
    identical frames."""
    out = []
    for i, beat in enumerate(beats[:ART_MAX_BEATS]):
        text = (beat.get("voiceover") or beat.get("text") or topic or "").strip()
        subject = text[:120] if text else topic[:120]
        shot = {
            "subject": subject,
            "composition": _COMPOSITIONS[i % len(_COMPOSITIONS)],
            "lighting": _LIGHTING[i % len(_LIGHTING)],
            "camera": _CAMERAS[i % len(_CAMERAS)],
            "style": style_hint or "clean modern editorial photography",
            "palette": "",
            "negative": _NEGATIVE,
            "source": "fallback",
        }
        out.append(shot)
    return out


def _parse_shots(text: str, n: int) -> list:
    """Parse the model's JSON, tolerating code fences and stray prose."""
    raw = (text or "").strip()
    if "```" in raw:
        chunks = [c for c in raw.split("```") if "[" in c or "{" in c]
        raw = chunks[0] if chunks else raw
        raw = raw.replace("json", "", 1).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end + 1])
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    shots = []
    for item in data[:n]:
        if not isinstance(item, dict):
            continue
        shots.append({
            "subject": str(item.get("subject", ""))[:200],
            "composition": str(item.get("composition", ""))[:120],
            "lighting": str(item.get("lighting", ""))[:120],
            "camera": str(item.get("camera", ""))[:120],
            "style": str(item.get("style", ""))[:120],
            "palette": str(item.get("palette", ""))[:120],
            "negative": str(item.get("negative", "")) or _NEGATIVE,
            "source": "llm",
        })
    return shots


def _brief(topic: str, beats: list, brand: dict, style_hint: str) -> str:
    lines = []
    for i, b in enumerate(beats[:ART_MAX_BEATS], start=1):
        lines.append(f'{i}. {(b.get("voiceover") or b.get("text") or "")[:180]}')
    visual_rules = ""
    try:
        visual_rules = str((brand or {}).get("visual_rules") or (brand or {}).get("visuals") or "")[:400]
    except Exception:
        visual_rules = ""
    return (
        "You are an art director for short-form vertical video. Turn each beat "
        "into ONE photographable shot.\n\n"
        f"TOPIC: {topic[:180]}\n"
        f"BRAND VISUAL RULES: {visual_rules or 'clean, modern, uncluttered'}\n"
        f"HOUSE STYLE: {style_hint or 'editorial photography'}\n\n"
        "BEATS:\n" + "\n".join(lines) + "\n\n"
        "Return ONLY a JSON array, one object per beat, with these exact keys:\n"
        '  subject      - the concrete thing in frame (a person, an object, a scene). '
        'NEVER an abstract idea, NEVER a sentence of narration.\n'
        "  composition  - framing and where the subject sits in frame\n"
        "  lighting     - light source, direction, mood\n"
        "  camera       - lens and depth of field\n"
        "  style        - visual treatment consistent across all beats\n"
        "  palette      - 2-3 dominant colours\n"
        "  negative     - what must not appear\n\n"
        "Rules: keep `style` and `palette` IDENTICAL across every beat so the reel "
        "looks like one piece. Vary composition and camera so no two frames match. "
        "No text or words in any image. No preamble, no markdown — JSON only."
    )


# --------------------------------------------------------------------- job

def direct(w: Worker, job: Job, ctx: AgentContext):
    bus = ctx.deps["bus"]
    sb = ctx.deps.get("supabase") and ctx.deps["supabase"]()
    item_id = job.payload.get("item_id")
    account_id = job.account_id or job.payload.get("account_id")
    script = job.payload.get("script") or {}
    if not script and sb and item_id:
        script = ((board_get(sb, item_id) or {}).get("payload") or {}).get("script") or {}
    topic = job.payload.get("topic") or script.get("title") or ""
    beats = script.get("beats") or []

    def _handoff(reason: str):
        job_of(w, "creative.render", {
            "item_id": item_id, "script": script,
            "style": job.payload.get("style", "cinemagraph"),
        }, parent=job, account_id=account_id, priority=job.priority)
        w.queue.complete(job, {"ok": True, "art": reason})

    if not ART_DIRECTOR_ENABLED or not beats:
        _handoff("skipped")
        return

    acct = load_account(sb, account_id) if (sb and account_id) else {}
    style_hint = ((acct or {}).get("config") or {}).get("art_style") or ""
    brand = brand_context_for(sb, account_id) if sb else {}

    bus.agent("architect", f"🎬 art-directing {len(beats)} beat(s) — \"{topic[:60]}\"",
              "info", "art_start", job_id=job.id, item_id=item_id)

    shots, label = [], "fallback"
    try:
        from agentcore.council import free_chat
        text, _cost, label = free_chat(_brief(topic, beats, brand, style_hint), max_tokens=900)
        shots = _parse_shots(text, len(beats))
    except Exception as e:
        bus.agent("architect", f"free models unavailable for art direction ({str(e)[:90]}) — "
                               f"using deterministic shot list ($0)",
                  "warn", "art_fallback", job_id=job.id, item_id=item_id)

    if len(shots) < len(beats[:ART_MAX_BEATS]):
        # partial or empty -> top up deterministically so every beat gets a shot
        fb = fallback_pack(beats, topic, style_hint)
        shots = shots + fb[len(shots):]
        if label == "fallback":
            label = "deterministic"

    # Write the prompt pack into the script the renderer already reads.
    for i, beat in enumerate(beats[:len(shots)]):
        shot = shots[i]
        beat["art"] = shot
        beat["visual_prompt"] = compose_prompt(shot, style_hint)
    script["beats"] = beats
    script["art_directed"] = {"at": time.time(), "source": label,
                              "shots": len(shots)}

    if sb and item_id:
        try:
            board_patch_payload(sb, item_id, {"script": script})
        except Exception:
            pass

    bus.agent("architect", f"🎬 {len(shots)} shot(s) directed via {label} — "
                           f"first shot: \"{(shots[0].get('subject') or '')[:70]}\"",
              "success", "art_done", job_id=job.id, item_id=item_id)
    _handoff(label)
