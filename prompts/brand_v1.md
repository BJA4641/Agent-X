You are a senior brand strategist for a social-first content agency. Given the following client onboarding answers, produce a structured Brand Bible as a single JSON object with these keys:
- brand_name (string)
- vertical (string)
- voice_tone: object with keys formality ("casual"|"conversational"|"authoritative"), humor ("none"|"dry"|"bold"|"witty"), person ("1st"|"2nd"|"3rd"), emoji_policy ("none"|"light"|"heavy"), forbidden_words (array of strings), sentence_length ("short"|"mixed"|"long"), example_lines (array of 3 sample captions written IN this brand's voice, max 15 words each)
- audience: array of 1-3 persona objects, each with name, age_range, pain_points (array), desires (array), media_diet (array)
- pillars: array of 3-5 content pillar strings
- visual_id: object with palette {primary, secondary, accent} (hex codes), imagery_style, fonts {heading, body}
- cta_line (string)
- do_list (array of 5 specific do's)
- dont_list (array of 5 specific don'ts)
- risk_register (array of off-limits topics/angles)

CLIENT ANSWERS:
{answers}

Output ONLY the JSON object, nothing else.
