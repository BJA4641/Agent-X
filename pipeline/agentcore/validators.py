"""validators.py — Pydantic schemas + validation helpers for content.

Production quality control pattern: every content type has a schema; LLM
output is validated against it; validation errors feed back as structured
instructions to the LLM for auto-retry.
"""
from __future__ import annotations
import re
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------- Scripts ----------------

class Beat(BaseModel):
    voiceover: str = Field(..., min_length=5, max_length=300)
    on_screen_text: Optional[str] = Field("", max_length=40)
    visual_prompt: str = Field(..., min_length=10, max_length=500)
    visual_source: Literal["broll","ui_mockup","poster","stock","text_card"] = "broll"
    camera: Literal["hold","slow_push","slide_r","tilt_up","zoom_punch","static","whip_pan"] = "slow_push"
    transition_in: Literal["cut","fade","whip","flash_white","zoom_punch"] = "cut"
    transition_out: Literal["cut","fade","whip","flash_white","zoom_punch"] = "cut"
    sfx: Literal["boom","whoosh","pop","click","riser","cash","none","tick"] = "none"
    duration_ms: int = Field(3500, ge=1200, le=6000)

    @field_validator("voiceover")
    @classmethod
    def no_forbidden(cls, v: str) -> str:
        banned = ["hey guys", "in today's video", "let's talk about", "game changer",
                  "revolutionary", "you won't believe", "get rich quick", "guaranteed income"]
        low = v.lower()
        for b in banned:
            if b in low:
                raise ValueError(f"voiceover contains forbidden phrase: '{b}'")
        return v


class Script(BaseModel):
    title: str = Field(..., min_length=5, max_length=120)
    hook: str = Field(..., min_length=2, max_length=80)
    beats: List[Beat] = Field(..., min_length=4, max_length=8)
    cta: str = Field("follow for one move a day.", min_length=3, max_length=80)
    hashtags: List[str] = Field(default_factory=list, max_length=15)
    caption: Optional[str] = Field("", max_length=500)
    pillar: Literal["quick_tip","deep_dive","mistake","results"] = "quick_tip"
    trend_pattern: Optional[str] = None
    total_ms: int = 0

    @model_validator(mode="after")
    def check_total(self):
        total = sum(b.duration_ms for b in self.beats) + 2500   # +CTA card
        self.total_ms = total
        if total < 15000:
            raise ValueError(f"video total duration {total}ms is too short (min 15000ms)")
        if total > 55000:
            raise ValueError(f"video total duration {total}ms is too long (max 55000ms)")
        return self


# ---------------- Quality grading ----------------

GRader_DIMENSIONS = ["hook", "visuals", "pacing", "audio", "caption", "cta"]

class DimensionScore(BaseModel):
    score: int = Field(..., ge=1, le=10)
    reason: str = Field("", min_length=0, max_length=300)


class GradeResult(BaseModel):
    hook: DimensionScore
    visuals: DimensionScore
    pacing: DimensionScore
    audio: DimensionScore
    caption: DimensionScore
    cta: DimensionScore
    overall: float = Field(default=0.0, ge=0, le=10)
    passed: bool = False
    fix_instruction: str = Field(..., min_length=10, max_length=500)
    strengths: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def calc_overall(self):
        scores = [self.hook.score, self.visuals.score, self.pacing.score,
                  self.audio.score, self.caption.score, self.cta.score]
        avg = sum(scores) / len(scores)
        self.overall = round(avg, 1)
        self.passed = avg >= 8.0 and min(scores) >= 6
        return self


# ---------------- SEO pack ----------------

class SEOPack(BaseModel):
    hashtags: List[str] = Field(..., min_length=4, max_length=15)
    first_comment: str = Field(..., min_length=10, max_length=200)
    alt_text: str = Field(..., min_length=10, max_length=200)
    yt_title: str = Field(..., min_length=10, max_length=100)

    @field_validator("hashtags")
    @classmethod
    def normalize_hashtags(cls, tags: List[str]) -> List[str]:
        out = []
        for t in tags:
            t = t.strip().lstrip("#").replace(" ", "")
            if t and t not in out:
                out.append("#" + t.lower())
        return out


# ---------------- Caption / Platform-copies ----------------

class PlatformCaptions(BaseModel):
    tiktok_caption: str = Field(..., min_length=10, max_length=300)
    ig_caption: str = Field(..., min_length=10, max_length=2200)
    yt_description: str = Field(..., min_length=10, max_length=5000)
    first_comment: str = Field(..., min_length=5, max_length=200)


# ---------------- Brand docs ----------------

class BrandBible(BaseModel):
    """The architect output must conform to this shape."""
    executive_summary: str = Field(..., min_length=200)
    vision_mission: str = Field(..., min_length=200)
    revenue_model: str = Field(..., min_length=200)
    brand_identity: str = Field(..., min_length=200)
    visual_identity: str = Field(..., min_length=200)
    marketing_strategy: str = Field(..., min_length=200)
    instagram_playbook: str = Field(..., min_length=100)
    tiktok_playbook: str = Field(..., min_length=100)
    youtube_playbook: str = Field(..., min_length=100)
    content_calendar: str = Field(..., min_length=200)
    content_rules: str = Field(..., min_length=200)
    hashtags_seo: str = Field(..., min_length=100)
    production_sop: str = Field(..., min_length=200)


def validate_dangerous_content(text: str) -> List[str]:
    """Return list of risk flags (empty = safe)."""
    flags = []
    low = text.lower()
    if re.search(r"\b(guaranteed income|get rich quick|make \$\d+ (per day|a day)|no risk|sure thing)", low):
        flags.append("financial_claim")
    if re.search(r"\b(cures|treats|miracle|proven by science)\b", low) and ("health" in low or "medical" in low or "dr." in low):
        flags.append("medical_claim")
    if re.search(r"\b(buy now|limited offer|act now|only today|click here)\b.*https?://", low):
        flags.append("spam_pattern")
    return flags
