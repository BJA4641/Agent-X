"""distribution.py — the marketing agent's first body: repurpose every clip
into a tweet, a LinkedIn post, and a newsletter blurb. Claude live, templates dry-run."""
import json
from . import config, ledger

EST_COST = 0.008

def repurpose(script: dict, topic: str, item_id=None) -> dict:
    if config.HAS_ANTHROPIC and ledger.budget_ok(EST_COST):
        try:
            import anthropic
            prompt, version = config.load_prompt("repurpose_v1")
            prompt = prompt.replace("{script}", json.dumps({"topic": topic, **script}))
            msg = anthropic.Anthropic().messages.create(
                model=config.get("CLAUDE_MODEL", "claude-sonnet-4-5"), max_tokens=500,
                messages=[{"role": "user", "content": prompt}])
            text = "".join(b.text for b in msg.content if b.type == "text")
            out = json.loads(text[text.find("{"): text.rfind("}") + 1])
            cost = (msg.usage.input_tokens * 3 + msg.usage.output_tokens * 15) / 1e6
            ledger.record("distribution", model=msg.model, prompt_version=version, cost_usd=cost, item_id=item_id)
            return {k: out.get(k, "") for k in ("tweet", "linkedin", "newsletter")}
        except Exception as e:
            ledger.record("distribution", ok=False, detail=str(e), item_id=item_id)
    hook = script.get("hook", topic)
    ledger.record("distribution", model="template", cost_usd=0, item_id=item_id)
    return {
        "tweet": f"{hook}\n\nNew 30-second breakdown just dropped — link in bio.",
        "linkedin": f"{hook}\n\nWe just published a 30-second breakdown of exactly how this works.\n\nWhat would you automate first?",
        "newsletter": f"{hook} This week's clip shows the whole move in 30 seconds.",
    }
