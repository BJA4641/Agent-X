# caption_v1
Write platform captions for this short video. Script: {script}
Return STRICT JSON only:
{"instagram": {"caption": str (hook line, 2 value lines, CTA line; <=2 emojis total), "hashtags": [str x5 specific niche tags, no # symbol]},
 "tiktok": {"caption": str (1 punchy line + 1 curiosity line, casual tone; <=1 emoji), "hashtags": [str x4 niche tags, no # symbol], "sound_note": str (what trending-sound vibe to search in the TikTok app, e.g. "calm lofi tech beat")},
 "youtube": {"title": str (<=90 chars, curiosity-first), "description": str (2 sentences + CTA), "tags": [str x6 search keywords]}}
No income claims, no "make money" language.
