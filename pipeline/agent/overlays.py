"""overlays.py — in-graphics: emoji callouts, progress dots, punch frames, end card.
Renders accent elements ON TOP of beat frames so videos have visual grammar
(circles, arrows, underlines, emoji reaction pops) like top Reels creators use.
"""
import os, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Concept → small circle badge labels (avoids emoji-font issues in PIL which
# can't render CBDT color emoji natively; labels look cleaner than tofu squares).
CONCEPT_LABELS = {
    "ai": ("AI",   (139, 92, 246)),
    "gpt": ("GPT", (16, 185, 129)),
    "chatgpt": ("GPT", (16, 185, 129)),
    "claude": ("CLAUDE", (255, 150, 50)),
    "gemini": ("GEM", (66, 133, 244)),
    "free": ("FREE", (16, 185, 129)),
    "money": ("$$$", (245, 158, 11)),
    "paid": ("PAID", (239, 68, 68)),
    "save": ("SAVE", (16, 185, 129)),
    "cost": ("COST", (245, 158, 11)),
    "secret": ("HACK", (139, 92, 246)),
    "hidden": ("HIDDEN", (139, 92, 246)),
    "stop": ("STOP", (239, 68, 68)),
    "wait": ("WAIT", (239, 68, 68)),
    "never": ("NEVER", (239, 68, 68)),
    "fast": ("FAST", (245, 158, 11)),
    "quick": ("QUICK", (245, 158, 11)),
    "easy": ("EASY", (16, 185, 129)),
    "simple": ("EASY", (16, 185, 129)),
    "instant": ("NOW", (239, 68, 68)),
    "video": ("REEL", (239, 68, 68)),
    "reel": ("REEL", (239, 68, 68)),
    "youtube": ("YT", (239, 68, 68)),
    "instagram": ("IG", (225, 48, 108)),
    "tiktok": ("TT", (0,0,0)),
    "phone": ("APP", (66,133,244)),
    "laptop": ("TIP", (59,130,246)),
    "email": ("MAIL", (59,130,246)),
    "code": ("CODE", (139,92,246)),
    "write": ("WRITE", (245,158,11)),
    "website": ("SITE", (59,130,246)),
    "browser": ("WEB", (59,130,246)),
    "chrome": ("CHROME", (59,130,246)),
    "app": ("APP", (66,133,244)),
    "tool": ("TOOL", (139,92,246)),
    "trick": ("HACK", (139,92,246)),
    "hack": ("HACK", (139,92,246)),
    "tip": ("TIP", (245,158,11)),
    "mistake": ("!ERR", (239,68,68)),
    "wrong": ("NO", (239,68,68)),
    "bad": ("BAD", (239,68,68)),
    "good": ("GOOD", (16,185,129)),
    "best": ("#1", (245,158,11)),
    "new": ("NEW", (16,185,129)),
    "views": ("EYES", (59,130,246)),
    "followers": ("FANS", (225,48,108)),
    "likes": ("LIKE", (239,68,68)),
}

def _pick_label(text: str):
    low = text.lower()
    for kw, (lab, col) in CONCEPT_LABELS.items():
        if kw in low:
            return lab, col
    # default: short 3-letter badge "TIP" in orange
    return random.choice([("TIP",(245,158,11)),("WOW",(139,92,246)),("PRO",(16,185,129)),("HOT",(239,68,68))])


def add_progress_dots(img: Image.Image, beat_idx: int, total_beats: int):
    """Small dots across the top showing beat position (like TikTok's segment bar)."""
    d = ImageDraw.Draw(img, "RGBA")
    if total_beats <= 1: return
    dot_w = 24
    gap = 12
    total = total_beats * dot_w + (total_beats-1) * gap
    x0 = (W - total) // 2
    y = 90
    for i in range(total_beats):
        x = x0 + i * (dot_w + gap)
        active = i <= beat_idx
        d.rounded_rectangle([x, y, x + dot_w, y + 6], radius=3,
                            fill=(255,255,255,230) if active else (255,255,255,70))


def add_corner_emoji(img: Image.Image, text: str, beat_idx: int):
    """Floating circular badge in the top-right corner: short uppercase label
    on a colored sticker (creator-common pattern-interrupt trope)."""
    label, color = _pick_label(text)
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy, r = W - 180, 200, 95
    # Circle
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*color, 240))
    # White ring
    d.ellipse([cx-r+8, cy-r+8, cx+r-8, cy+r-8], outline=(255,255,255,220), width=6)
    # Label
    try:
        fs = 56 if len(label) <= 3 else 44
        font = ImageFont.truetype(FONT_BOLD, fs)
    except Exception:
        font = None
    bbox = d.textbbox((0,0), label, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    off = int(4 * math.sin(beat_idx))
    d.text((cx - tw//2, cy - th//2 - 8 + off), label, font=font, fill=(255,255,255,255))


def add_hook_badge(img: Image.Image, hook_text: str):
    """Beat-0 hook overlay: giant STOP / WAIT-style pattern interrupt."""
    d = ImageDraw.Draw(img, "RGBA")
    # Top red band
    d.rectangle([0, 180, W, 380], fill=(239, 68, 68, 230))
    try:
        font_big = ImageFont.truetype(FONT_BOLD, 110)
    except Exception:
        font_big = None
    word = hook_text.upper()
    if len(word) > 14: word = word[:14]
    bbox = d.textbbox((0,0), word, font=font_big)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw)//2, 205), word, font=font_big, fill=(255,255,255,255))


def add_number_circle(img: Image.Image, n: int, total: int):
    """Big circle with step number in bottom-right corner."""
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy, r = W - 180, H - 520, 80
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255,255,255,240))
    try:
        font = ImageFont.truetype(FONT_BOLD, 90)
    except Exception:
        font = None
    txt = str(n+1)
    bbox = d.textbbox((0,0), txt, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    d.text((cx - tw//2, cy - th//2 - 8), txt, font=font, fill=(15,15,15,255))


def add_brand_watermark(img: Image.Image, brand: str = "AGENT-X"):
    """Small bottom-left logo watermark."""
    d = ImageDraw.Draw(img, "RGBA")
    try:
        font = ImageFont.truetype(FONT_BOLD, 36)
    except Exception:
        font = None
    d.text((60, H-120), brand, font=font, fill=(255,255,255,160))


def add_cta_card(img: Image.Image, cta_text: str):
    """End card: big centered card with CTA + follow icon."""
    d = ImageDraw.Draw(img, "RGBA")
    # Darken background
    d.rectangle([0,0,W,H], fill=(0,0,0,140))
    # Rounded card
    card = [100, H//2-300, W-100, H//2+300]
    d.rounded_rectangle(card, radius=40, fill=(20,20,30,245))
    try:
        font_big = ImageFont.truetype(FONT_BOLD, 90)
        font_med = ImageFont.truetype(FONT_BOLD, 60)
    except Exception:
        font_big = font_med = None
    # plus / follow icon
    plus = "➕  FOLLOW"
    bbox = d.textbbox((0,0), plus, font=font_med)
    d.rounded_rectangle([(W-(bbox[2]-bbox[0]))//2-30, H//2-240, (W+(bbox[2]-bbox[0]))//2+30, H//2-140],
                        radius=20, fill=(239,68,68,255))
    d.text(((W-(bbox[2]-bbox[0]))//2, H//2-225), plus, font=font_med, fill=(255,255,255,255))
    # CTA wrapped
    words = cta_text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur+" "+w).strip()
        bbox = d.textbbox((0,0), trial, font=font_big)
        if bbox[2]-bbox[0] > W-260:
            lines.append(cur); cur = w
        else:
            cur = trial
    if cur: lines.append(cur)
    y = H//2 - 60
    for line in lines[:4]:
        bbox = d.textbbox((0,0), line, font=font_big)
        d.text(((W-(bbox[2]-bbox[0]))//2, y), line, font=font_big, fill=(255,255,255,255))
        y += 110


def decorate_frame(img: Image.Image, beat_text: str, beat_idx: int, total_beats: int,
                   style: str, is_hook: bool = False, is_cta: bool = False,
                   cta_text: str = "", hook_word: str = ""):
    """Apply all overlay layers to a beat frame. Called by visuals.beat_frame."""
    add_progress_dots(img, beat_idx, total_beats)
    add_brand_watermark(img)

    if is_hook and hook_word:
        add_hook_badge(img, hook_word)
    else:
        add_corner_emoji(img, beat_text, beat_idx)

    if 0 < beat_idx < total_beats - (1 if is_cta else 0):
        add_number_circle(img, beat_idx-1 if is_hook else beat_idx, total_beats-2)

    if is_cta:
        add_cta_card(img, cta_text)
