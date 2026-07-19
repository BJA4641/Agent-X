"""seo.py v4.3 — SEO / Hashtag Agent.
Responsibility:
  - Select optimal hashtag sets per post based on the account's hashtags_seo doc
  - Generate first-comment pin text for engagement
  - Generate alt text / description for IG/YT accessibility
  - Suggest SEO title for YouTube shorts
  - Pull hashtags from the account's hashtags_seo doc if available

Runs after brain writes a script (and after video render). Does NOT call LLMs —
pure heuristic + doc lookup — so it's near-free and never fails the pipeline.

Inputs:   topic, script, account_id, project_id, captions, item_id
Outputs:  {hashtags, first_comment, alt_text, yt_title}
Depends:  brain (script exists), architect (hashtag doc exists via memory)
"""
from . import config, events
import random, re
try:
    from . import memory
except Exception as _e:
    print(f"[seo] WARNING: memory import failed ({_e}); using no-op stub.")
    from . import _memstub
    memory = _memstub.MemoryStub()

NICHE_DEFAULT_HASHTAGS = {
  "ai_tools": {
    "big":   ["fyp","viral","foryou","foryoupage","tiktok","trending","reels","shorts","learn","tech"],
    "mid":   ["aitools","techtok","productivity","learnai","sidehustle","tipsandtricks","howto","tutorial","aihacks","chatgpt"],
    "niche": ["aitoolsdaily","aiupdates","dailytips","aitips","promptengineering","chatgpttips","freeaitools","aitricks"],
  },
  "cats": {
    "big":   ["cat","cats","catsofinstagram","catlover","pet","pets","viral","cute","fyp","shorts"],
    "mid":   ["catlife","catlove","kitten","kitty","catlovers","meow","catvideo","funnycat","cutecat","catfacts"],
    "niche": ["catfactsdaily","catmoments","dailymews","catoftheday","catbehavior","catcaretips","meowdaily"],
  },
  "fitness": {
    "big":   ["fyp","fitness","gym","workout","viral","shorts","trending","fit","motivation"],
    "mid":   ["gymtok","fitnessmotivation","homeworkout","fitnesstips","workoutroutine","gymlife","bodybuilding","weightloss"],
    "niche": ["dailyfitnesstips","workoutideas","homegymlife","fitnesshacks","gymtipsdaily"],
  },
  "cooking": {
    "big":   ["food","cooking","recipe","foodie","fyp","viral","shorts","yummy","tasty","easyrecipe"],
    "mid":   ["cookingtiktok","foodtok","homecooking","easyrecipes","quickmeals","recipevideo","cookingtips","foodhacks"],
    "niche": ["dailyrecipetips","30minmeals","homecookedaily","easycookinghacks"],
  },
  "default": {
    "big":   ["fyp","viral","foryou","foryoupage","tiktok","trending","reels","shorts","learn","tips"],
    "mid":   ["tipsandtricks","howto","tutorial","lifehack","growth","learn","sidehustle","dailytips"],
    "niche": ["dailytips101","learnwithme","quicktips","tricksandtips"],
  },
}


def _hashtag_set_for_account(account_id, project_id) -> dict:
    """Try to parse the account's hashtags_seo doc; fall back to defaults."""
    # Look up doc from Supabase if available
    tag_doc_text = ""
    if config.HAS_SUPABASE and account_id:
        try:
            from supabase import create_client
            sb = create_client(config.get("SUPABASE_URL"), config.supabase_service_key())
            row = (sb.table("account_documents")
                   .select("content").eq("account_id", account_id)
                   .eq("doc_type", "hashtags_seo").limit(1).execute())
            if row.data:
                tag_doc_text = row.data[0].get("content","") or ""
        except Exception:
            tag_doc_text = ""
    if not tag_doc_text:
        return NICHE_DEFAULT_HASHTAGS["default"]

    # Best-effort: pick tags by matching any # prefixed words, bucket by size
    tags = re.findall(r"#([a-zA-Z0-9_]+)", tag_doc_text)
    if not tags:
        return NICHE_DEFAULT_HASHTAGS["default"]
    big, mid, niche_t = [], [], []
    for t in tags:
        tl = t.lower()
        if tl in NICHE_DEFAULT_HASHTAGS["default"]["big"]:
            big.append(tl)
        elif len(tl) >= 12:
            niche_t.append(tl)
        else:
            mid.append(tl)
    # Fill gaps with defaults
    def _fill(lst, defaults, n):
        out = list(dict.fromkeys(lst))
        for d in defaults:
            if len(out) >= n: break
            if d not in out: out.append(d)
        return out[:n]
    return {
      "big":   _fill(big,   NICHE_DEFAULT_HASHTAGS["default"]["big"],   3),
      "mid":   _fill(mid,   NICHE_DEFAULT_HASHTAGS["default"]["mid"],   4),
      "niche": _fill(niche_t, NICHE_DEFAULT_HASHTAGS["default"]["niche"], 3),
    }


def seoize(topic: str, script: dict, account_id=None, project_id=None,
           captions: dict = None, item_id: str = None) -> dict:
    """Return {hashtags, first_comment, alt_text, yt_title}."""
    sets = _hashtag_set_for_account(account_id, project_id)
    big = random.sample(sets["big"], min(3, len(sets["big"])))
    mid = random.sample(sets["mid"], min(4, len(sets["mid"])))
    niche_t = random.sample(sets["niche"], min(3, len(sets["niche"])))
    final_tags = list(dict.fromkeys(big + mid + niche_t))[:10]
    # Prefix # for publishing
    hashtags = [t if t.startswith("#") else f"#{t}" for t in final_tags]

    hook = (script.get("hook") or topic or "").strip()
    title = script.get("title") or hook or topic
    cta = script.get("cta") or "follow for more"

    # Pin-first-comment: rotate between 3 options
    comment_pool = [
        "💡 which tip are you trying first? drop it in the comments 👇",
        "🔥 save this for later so you don't forget",
        "comment 'LINK' and i'll send the resource to you 🔗",
        "follow for one move a day 🚀",
    ]
    first_comment = random.choice(comment_pool)
    alt_text = f"Short-form video: {title[:80]}."
    yt_title = (hook.replace(".", "").replace("!", "")[:70] + " #shorts").strip()

    return {
        "hashtags": hashtags,
        "first_comment": first_comment,
        "alt_text": alt_text[:200],
        "yt_title": yt_title[:100],
    }
