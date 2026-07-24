"""visuals.py v2 — agency-grade beat frames.
v1 used: static Gemini image + big black scrim + centered paragraph text.
v2 uses:
  - Hook frame: HIGH-CONTRAST pattern-interrupt (giant keyword on color, emoji sticker, red band)
  - Body beats: cinematic Gemini image OR rich procedural gradient + vignette + film grain
               + corner emoji sticker + progress dots + step numbers + brand watermark
               (text is NO LONGER baked into the image — word-by-word captions are burned
                in at the edit stage via ASS subtitles for kinetic pop.)
  - CTA / end-card frame: dark card with big follow CTA
"""
import base64, json, math, os, random, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from . import config, ledger, overlays

W, H = 1080, 1920
EST_COST = 0.04

# Stronger, trendier art directions — one per video so frames MATCH
STYLES = {
    "tech-noir": {
        "prompt": "dark futuristic tech aesthetic, neon cyan and magenta accents on near-black, glossy UI elements, depth of field, cinematic 9:16 vertical",
        "bg_top": (10, 12, 28), "bg_bot": (80, 30, 140),
        "accent": (0, 229, 255),
    },
    "editorial-pop": {
        "prompt": "minimalist editorial illustration, bold flat geometric shapes, generous white/cream negative space, limited 3-color palette, trendy magazine layout",
        "bg_top": (250, 244, 235), "bg_bot": (240, 180, 160),
        "accent": (215, 88, 41),
    },
    "cinematic-stock": {
        "prompt": "cinematic photograph shot on 35mm film, shallow depth of field, moody golden-hour window light, soft film grain, photorealistic",
        "bg_top": (20, 16, 24), "bg_bot": (110, 80, 60),
        "accent": (240, 200, 140),
    },
    "clay-3d": {
        "prompt": "soft 3D clay render, rounded friendly shapes, pastel studio lighting, playful isometric diorama, smooth shadows, premium Apple-style product render",
        "bg_top": (250, 238, 232), "bg_bot": (255, 180, 180),
        "accent": (255, 120, 140),
    },
    "meme-energetic": {
        "prompt": "vibrant high-contrast pop-art composition, bold halftone dots, primary colors, playful collage energy, vertical 9:16 for TikTok/Reels",
        "bg_top": (20, 20, 40), "bg_bot": (255, 60, 80),
        "accent": (255, 220, 0),
    },
    "glass-minimal": {
        "prompt": "glassmorphism UI, translucent frosted layers, soft internal glow, subtle gradient mesh, premium fintech aesthetic, clean vertical 9:16",
        "bg_top": (14, 20, 48), "bg_bot": (80, 60, 180),
        "accent": (120, 200, 255),
    },
    "retro-wave": {
        "prompt": "1980s synthwave aesthetic, hot pink and electric purple, chrome accents, grid horizon, retro sun, nostalgic VHS grain",
        "bg_top": (20, 0, 40), "bg_bot": (255, 80, 180),
        "accent": (0, 230, 255),
    },
    "nature-calm": {
        "prompt": "soft nature bokeh photography, sunlit leaves, warm golden hour, gentle blur, calm and premium atmosphere, 9:16 vertical",
        "bg_top": (20, 40, 30), "bg_bot": (180, 140, 80),
        "accent": (255, 220, 150),
    },
}

def pick_style(item_id, override: str = None) -> str:
    if override in STYLES: return override
    env = config.get("STYLE", "auto")
    if env in STYLES: return env
    import hashlib
    return list(STYLES)[int(hashlib.sha256(str(item_id).encode()).hexdigest(), 16) % len(STYLES)]


_gemini_cooldown_until = 0.0

def beat_frame(text: str, image_prompt: str, out_path: str, seed: int = 0,
               item_id=None, style: str = None, beat_idx: int = 0, total_beats: int = 0,
               hook_word: str = "", cta_text: str = "") -> str:
    """Render ONE beat frame. text is the beat's spoken line but we DON'T burn
    it into the image anymore (captions are done in edit via ASS for kinetic feel)."""
    global _gemini_cooldown_until
    style = style or pick_style(item_id)
    spec = STYLES.get(style, STYLES["tech-noir"])
    is_hook = (beat_idx == 0)
    is_cta  = (total_beats > 0 and beat_idx == total_beats - 1)

    bg = None
    used_ai = False
    # v5.5 P0 FIX: try aisuite first (honors /dashboard/models model_t2i selection),
    # then fall back to legacy Gemini direct call, then procedural gradient.
    from agentcore.config import econ_mode_on as _econ
    if ledger.budget_ok(EST_COST) and time.time() >= _gemini_cooldown_until and not is_cta and not _econ():
        # 1) aisuite (catalog-driven, user-selectable providers) — skipped in econ mode
        try:
            from agentcore import aisuite
            full_prompt = (
                spec["prompt"] + ". " + image_prompt
                + ". Vertical 9:16, NO TEXT whatsoever, no logos, no watermarks, no words. "
                "Leave the bottom 30% of the frame relatively dark/neutral so subtitles can sit there. "
                "High energy, premium, modern creator aesthetic."
            )
            t0 = time.time()
            path = aisuite.generate_image(full_prompt, size="1080x1920")
            bg = Image.open(path).convert("RGB")
            ledger.record("visuals", model="aisuite:t2i", cost_usd=EST_COST, item_id=item_id,
                          latency=time.time()-t0)
            used_ai = True
        except Exception as e:
            ledger.record("visuals", ok=False, model="aisuite:t2i", detail=f"aisuite fail: {str(e)[:120]}",
                          item_id=item_id)
    # 2) Legacy Gemini direct (backup if aisuite fails or no key)
    if bg is None and config.HAS_GEMINI and ledger.budget_ok(EST_COST) and time.time() >= _gemini_cooldown_until and not is_cta:
        try:
            time.sleep(float(config.get("GEMINI_DELAY", "6.5")))
            full_prompt = (
                spec["prompt"] + ". " + image_prompt
                + ". Vertical 9:16, NO TEXT whatsoever, no logos, no watermarks, no words. "
                "Leave the bottom 30% of the frame relatively dark/neutral so subtitles can sit there. "
                "High energy, premium, modern creator aesthetic."
            )
            bg = _gemini_image(full_prompt)
            ledger.record("visuals", model=config.get("NANO_BANANA_MODEL", "gemini-2.5-flash-image"),
                          cost_usd=EST_COST, item_id=item_id)
            used_ai = True
        except Exception as e:
            ledger.record("visuals", ok=False, detail=str(e)[:200], item_id=item_id)
            if "429" in str(e):
                _gemini_cooldown_until = time.time() + 600
    # 2.5) FREE, KEYLESS image generation — v5.11.9 REQ-VISUALS-REAL.
    #
    # Root cause of "why is the background a still colour": on 2026-07-24 every
    # frame of all three published reels fell through to the procedural gradient.
    # run_ledger showed aisuite:t2i "all t2i providers failed: fal timed out",
    # a gemini 429, and then rich-gradient-v2 SIXTEEN times — silently, at $0.
    # The reels looked like coloured slides because no image was ever generated.
    #
    # Pollinations needs no API key, no quota and no billing, so it is the right
    # last line of defence before giving up on imagery altogether. It should be
    # tried on EVERY failure of the paid ladder, not skipped.
    if bg is None and not is_cta:
        try:
            from urllib.parse import quote as _q
            import urllib.request as _u
            free_prompt = (image_prompt or spec.get("prompt") or "")[:380]
            url = ("https://image.pollinations.ai/prompt/" + _q(free_prompt)
                   + f"?width=1080&height=1920&nologo=true&seed={abs(hash((item_id, seed))) % 99999}")
            req = _u.Request(url, headers={"User-Agent": "agentx/5.11.9"})
            with _u.urlopen(req, timeout=90) as r:
                data = r.read()
            import io as _io
            bg = Image.open(_io.BytesIO(data)).convert("RGB")
            ledger.record("visuals", model="pollinations-free", cost_usd=0, item_id=item_id)
            used_ai = True
        except Exception as e:
            ledger.record("visuals", ok=False, model="pollinations-free",
                          detail=f"free image fallback failed: {str(e)[:120]}", item_id=item_id)

    # 3) Procedural fallback — LAST resort, and no longer silent.
    if bg is None:
        bg = _rich_background(seed, style)
        ledger.record("visuals", ok=False, model="rich-gradient-v2", cost_usd=0, item_id=item_id,
                      detail="NO IMAGE GENERATED — every provider failed, frame is a plain "
                             "gradient. This is why a reel looks like coloured slides.")
        _note_gradient_fallback(item_id)

    # Resize to 1080x1920 exactly
    bg = bg.resize((W, H)).convert("RGB")

    # Post-processing on AI images to make them feel more "Reels"
    if used_ai:
        bg = _apply_looks(bg, style)

    # Apply overlays (progress dots, corner emoji, step numbers, hook banner, end card)
    overlays.decorate_frame(bg, text, beat_idx, total_beats, style,
                            is_hook=is_hook, is_cta=is_cta,
                            cta_text=cta_text, hook_word=hook_word)
    bg.save(out_path, quality=92)
    return out_path


def hook_poster_frame(hook_text: str, out_path: str, item_id=None, style: str = None):
    """Bonus beat-0 pattern-interrupt poster: 2 words max, high contrast, no AI image."""
    style = style or "meme-energetic"
    spec = STYLES.get(style, STYLES["meme-energetic"])
    img = _rich_background(0, style)
    d = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 200)
    except Exception:
        font = None
    # giant centered word
    words = hook_text.upper().split()[:2]
    line = " ".join(words)
    bbox = d.textbbox((0,0), line, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    # black highlight block
    d.rectangle([0, H//2-th//2-60, W, H//2+th//2+60], fill=(0,0,0,200))
    d.text(((W-tw)//2, H//2 - th//2 - 20), line, font=font, fill=spec["accent"])
    img.save(out_path, quality=92)
    return out_path


def _gemini_image(prompt: str) -> Image.Image:
    key = config.get("GEMINI_API_KEY") or config.get("GOOGLE_API_KEY")
    model = config.get("NANO_BANANA_MODEL", "gemini-2.5-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    for part in data["candidates"][0]["content"]["parts"]:
        if "inlineData" in part:
            raw = base64.b64decode(part["inlineData"]["data"])
            from io import BytesIO
            return Image.open(BytesIO(raw)).convert("RGB")
    raise RuntimeError("no image in Gemini response")


def _rich_background(seed: int, style: str) -> Image.Image:
    """Procedural background v2: two-point gradient + radial vignette + noise grain +
    subtle orb / mesh shape in the accent color so it doesn't look like a flat color bar."""
    spec = STYLES.get(style, STYLES["tech-noir"])
    top = list(spec["bg_top"])
    bot = list(spec["bg_bot"])
    # per-beat hue shift for variety within one video
    shift = seed * 4
    top = tuple(min(255, max(0, c + shift - i*2)) for i, c in enumerate(top))
    bot = tuple(min(255, max(0, c - shift + i*2)) for i, c in enumerate(bot))

    img = Image.new("RGB", (W, H))
    px = img.load()
    for y in range(H):
        t = y / H
        # slight curve so gradient is more cinematic (darker at edges)
        base = tuple(int(top[i] + (bot[i]-top[i]) * (t**1.3)) for i in range(3))
        for x in range(W):
            px[x, y] = base

    # Add a big soft colored orb for depth
    orb = Image.new("RGBA", (W, H), (0,0,0,0))
    od = ImageDraw.Draw(orb, "RGBA")
    cx = random.Random(seed).randint(100, W-100)
    cy = random.Random(seed+1).randint(200, H-500)
    r  = random.Random(seed+2).randint(400, 800)
    ac = spec["accent"]
    for i in range(r, 0, -20):
        a = int(40 * (i/r) ** 2)
        od.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(*ac, a))
    orb = orb.filter(ImageFilter.GaussianBlur(80))
    img = Image.alpha_composite(img.convert("RGBA"), orb).convert("RGB")

    # Vignette (darken corners)
    vign = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vign)
    vd.ellipse([-W//3, -H//4, W+W//3, H+H//4], fill=255)
    vign = vign.filter(ImageFilter.GaussianBlur(300))
    dark = Image.new("RGB", (W, H), (0,0,0))
    img = Image.composite(img, dark, vign)

    # Fine film grain
    import numpy as np
    try:
        arr = np.array(img).astype("int16")
        noise = np.random.RandomState(seed).normal(0, 8, arr.shape).astype("int16")
        arr = np.clip(arr + noise, 0, 255).astype("uint8")
        img = Image.fromarray(arr)
    except Exception:
        pass

    return img


def _apply_looks(img: Image.Image, style: str) -> Image.Image:
    """Color grade AI images a bit so they feel 'produced', not raw."""
    # Slight contrast bump + saturation + bottom-darkening for subtitle safety
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Color(img).enhance(1.10)
    # Darken a band at the bottom where ASS captions will sit
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(overlay, "RGBA")
    d.rectangle([0, H-620, W, H], fill=(0,0,0,90))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(0.3))
    return img


# --------------------------------------------------------------- v5.11.9

def _note_gradient_fallback(item_id=None):
    """Make gradient frames VISIBLE to the operator.

    Sixteen gradient frames were produced across three reels without a single
    warning anywhere — the fallback recorded a $0 ledger line and nothing else,
    so a reel with no imagery at all looked like a successful render.
    """
    try:
        from agentcore.runtime import get_runtime
        rt = get_runtime()
        sb = rt.deps.get("supabase") and rt.deps["supabase"]()
        if sb is None:
            return
        row = (sb.table("settings").select("value").eq("key", "visuals_health")
               .limit(1).execute().data or [{}])
        val = (row[0].get("value") if row else {}) or {}
        val["gradient_frames"] = int(val.get("gradient_frames") or 0) + 1
        val["last_gradient_at"] = time.time()
        val["last_item"] = str(item_id or "")
        val["meaning"] = ("Frames rendered as a plain gradient because every image "
                          "provider failed. Reels will look like coloured slides.")
        sb.table("settings").upsert(
            {"tenant_id": os.environ.get("TENANT_ID", "me"),
             "key": "visuals_health", "value": val},
            on_conflict="tenant_id,key").execute()
    except Exception:
        pass
