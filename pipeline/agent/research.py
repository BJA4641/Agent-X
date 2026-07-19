"""research.py — Research Agent.
Responsibility:
  - Pull niche research (keywords, competitor angles, top questions audience asks)
  - Stores findings in memory for strategist/brain to use
  - Runs once per new account before strategist plans posts; very cheap (mostly curated templates)

Inputs:   niche, account brand docs
Outputs:  writes research findings into memory_entries (role=research)
Depends:  architect (needs to know account niche/angle)
"""
from . import config, events, llm, ledger
try:
    from . import memory
except Exception as _e:
    print(f"[research] WARNING: memory import failed ({_e}); using no-op stub.")
    from . import _memstub
    memory = _memstub.MemoryStub()
import json


NICHE_RESEARCH = {
  "ai_tools": {
    "top_questions": ["what is the best ai tool for __", "free ai tools for __", "chatgpt prompts for __", "ai tools no one knows about", "how to use ai to __"],
    "competitor_angles": ["daily AI tool demos", "prompt copy-paste", "hidden features you missed", "AI vs human comparisons", "free vs paid breakdowns"],
    "keywords": ["best ai tools", "chatgpt tutorial", "free ai", "ai productivity", "ai side hustle", "ai tools 2026"],
  },
  "cats": {
    "top_questions": ["why does my cat __", "how to stop cat from __", "best cat toys", "cat body language", "signs your cat is happy"],
    "competitor_angles": ["cat behavior decoded", "cute cat moments", "cat care 101", "cat product reviews", "funny cat reactions"],
    "keywords": ["cat facts", "cat behavior", "cat care", "cute cats", "cat tips", "cat toys"],
  },
  "pets": {
    "top_questions": ["how to train __", "best food for __", "signs __ is sick", "__ behavior meaning", "how to groom __"],
    "competitor_angles": ["pet training in 30s", "pet facts you didn't know", "cute pet moments", "product reviews", "care checklists"],
    "keywords": ["pet tips", "dog training", "cat facts", "pet care", "cute pets", "pet products"],
  },
}


def research_account(account_id: str, niche: str, handle: str, angle: str, project_id=None) -> dict:
    """Generate a compact research brief for the account and save to memory."""
    findings = _research(niche, angle)
    note = (f"RESEARCH BRIEF for @{handle} ({niche}):\n"
            f"- Top audience questions: {', '.join(findings['top_questions'][:5])}\n"
            f"- Working competitor angles: {', '.join(findings['competitor_angles'][:5])}\n"
            f"- Keywords/SEO: {', '.join(findings['keywords'][:8])}\n"
            f"Clone the ANGLES — never repost content.")
    memory.add(account_id=account_id, project_id=project_id, role="research", content=note,
              metadata={"niche": niche, "questions": findings["top_questions"]})
    events.emit("research", f"Compiled research brief for @{handle} — {len(findings['keywords'])} keywords.",
                "success", "research_done")
    return findings


def _research(niche: str, angle: str) -> dict:
    if niche in NICHE_RESEARCH:
        return NICHE_RESEARCH[niche]
    # Generic LLM research if budget allows
    if llm.ready() and ledger.budget_ok(0.02):
        try:
            prompt = (f"Niche: {niche}. Angle: {angle}. "
                      "Return JSON with {top_questions:[5 strings], competitor_angles:[5 strings],"
                      " keywords:[10 strings]} for short-form content in this niche. "
                      "Questions people actually Google/TikTok search; angles proven to work.")
            text, cost, _ = llm.chat(prompt, max_tokens=600)
            ledger.record("research", cost_usd=cost, detail=niche)
            parsed = json.loads(text[text.find("{"):text.rfind("}")+1])
            return {
              "top_questions": parsed.get("top_questions", [])[:5],
              "competitor_angles": parsed.get("competitor_angles", [])[:5],
              "keywords": parsed.get("keywords", [])[:10],
            }
        except Exception:
            pass
    return {
      "top_questions": [f"best {niche} tips", f"how to {niche}", f"{niche} for beginners",
                       f"{niche} mistakes to avoid", f"free {niche} tools"],
      "competitor_angles": ["daily tips", "mistakes to avoid", "reaction/review", "step-by-step", "numbered lists"],
      "keywords": [niche, f"{niche} tips", f"{niche} tutorial", f"best {niche}", f"{niche} for beginners",
                   f"how to {niche}", f"{niche} hack", f"{niche} 2026"],
    }
