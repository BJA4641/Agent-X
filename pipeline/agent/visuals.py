"""visuals.py — one 1080x1920 background per beat.
Gemini image model (live) or branded gradient (dry-run), caption on a scrim either way."""
import base64, json, math, os, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from . import config, ledger

W, H = 1080, 1920
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
EST_COST = 0.04  # per image guard

# 8 tuned art directions. One style per video (keyed by item id) so every frame matches.
STYLES = {
    "editorial": {"prompt": "minimalist editorial illustration, bold flat geometric shapes, generous negative space, limited palette",
                  "palette": ((244, 241, 234), (215, 88, 41))},
    "neon":      {"prompt": "dark futuristic tech aesthetic, neon glow accents on near-black, sleek minimal 3D",
                  "palette": ((8, 10, 22), (0, 229, 255))},
    "clay":      {"prompt": "soft 3D clay render, rounded friendly shapes, pastel studio lighting, playful",
                  "palette": ((250, 235, 227), (255, 154, 158))},
    "collage":   {"prompt": "paper cut-out collage, layered torn textures, hand-crafted analog look",
                  "palette": ((240, 230, 210), (90, 70, 160))},
    "cinematic": {"prompt": "cinematic photograph, shallow depth of field, moody natural window light, film grain",
                  "palette": ((18, 16, 20), (120, 100, 80))},
    "blueprint": {"prompt": "technical blueprint style, precise white line diagrams on deep engineering blue",
                  "palette": ((10, 30, 66), (120, 170, 255))},
    "retro":     {"prompt": "retro screen-print poster, grainy halftone texture, 1970s color palette",
                  "palette": ((242, 226, 190), (200, 60, 50))},
    "glass":     {"prompt": "glassmorphism, translucent frosted layers, soft internal glow, premium fintech look",
                  "palette": ((14, 18, 40), (110, 90, 220))},
}

def pick_style(item_id, override: str = None) -> str:
    if override in STYLES:
        return override
    env = config.get("STYLE", "auto")
    if env in STYLES:
        return env
    import hashlib
    return list(STYLES)[int(hashlib.sha256(str(item_id).encode()).hexdigest(), 16) % len(STYLES)]

def beat_frame(text: str, image_prompt: str, out_path: str, seed: int = 0, item_id=None, style: str = None) -> str:
    style = style or pick_style(item_id)
    bg = None
    if config.HAS_GEMINI and ledger.budget_ok(EST_COST):
        try:
            bg = _gemini_image(f"{STYLES[style]['prompt']}. {image_prompt}")
            ledger.record("visuals", model=config.get("NANO_BANANA_MODEL", "gemini-image"),
                          cost_usd=EST_COST, item_id=item_id)
        except Exception as e:
            ledger.record("visuals", ok=False, detail=str(e), item_id=item_id)
    if bg is None:
        bg = _gradient(seed, style)
        ledger.record("visuals", model="gradient-fallback", cost_usd=0, item_id=item_id)
    img = bg.resize((W, H)).filter(ImageFilter.GaussianBlur(0))
    _scrim_caption(img, text)
    img.save(out_path, quality=92)
    return out_path

def _gemini_image(prompt: str) -> Image.Image:
    key = config.get("GEMINI_API_KEY") or config.get("GOOGLE_API_KEY")
    model = config.get("NANO_BANANA_MODEL", "gemini-2.5-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {"contents": [{"parts": [{"text": f"{prompt}. Vertical 9:16 cinematic, no text, no watermark."}]}]}
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

def _gradient(seed: int, style: str = "neon") -> Image.Image:
    a, b = STYLES.get(style, STYLES["neon"])["palette"]
    # per-beat depth shift so frames of one video share the palette but breathe
    a = tuple(min(255, c + seed * 6) for c in a)
    img = Image.new("RGB", (W, H))
    for y in range(H):
        t = y / H
        img.paste(tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)), (0, y, W, y + 1))
    return img

def _scrim_caption(img: Image.Image, text: str):
    d = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(FONT, 84)
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=font) > W - 160:
            lines.append(cur); cur = w
        else:
            cur = trial
    lines.append(cur)
    lh = 104; block_h = lh * len(lines)
    y0 = H // 2 - block_h // 2
    d.rectangle([60, y0 - 60, W - 60, y0 + block_h + 60], fill=(0, 0, 0, 150))
    for i, line in enumerate(lines):
        x = (W - d.textlength(line, font=font)) // 2
        d.text((x, y0 + i * lh), line, font=font, fill=(255, 255, 255, 255))
