"""v5.8.7 regression tests — cost-mode gate, key aliases, provider cooldowns."""
import time
from agentcore import costmode

def test_alias_keys(monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("ELEVEN_API_KEY", "x")
    assert costmode.has_key("elevenlabs") is True   # alias must count

def test_free_providers_usable_in_free_only(monkeypatch):
    monkeypatch.setattr(costmode, "mode", lambda: "free_only")
    monkeypatch.setattr(costmode, "provider_state", lambda p: "ok")
    assert costmode.usable("gemini", paid=False) is True
    assert costmode.usable("groq", paid=True) is True      # free provider, still allowed
    assert costmode.usable("anthropic", paid=True) is False  # paid suspended

def test_error_classification():
    assert costmode._classify(402, "") == "out_of_credit"
    assert costmode._classify(0, "Insufficient credits") == "out_of_credit"
    assert costmode._classify(401, "") == "dead_key"
    assert costmode._classify(429, "") == "rate_limited"
    assert costmode._classify(500, "boom") == ""           # transient -> no cooldown

def test_cooldown_expiry(monkeypatch):
    monkeypatch.setattr(costmode, "_load", lambda force=False: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    costmode._CACHE["health"] = {"anthropic": {"state": "out_of_credit",
                                               "cooldown_until": time.time() - 5}}
    assert costmode.provider_state("anthropic") == "ok"    # expired cooldown clears
    costmode._CACHE["health"] = {"anthropic": {"state": "out_of_credit",
                                               "cooldown_until": time.time() + 500}}
    assert costmode.provider_state("anthropic") == "out_of_credit"


# ---- v5.8.8 spend policy ----
def test_policy_blocks_paid_thinking(monkeypatch):
    monkeypatch.setattr(costmode, "policy",
                        lambda: {"paid_art": True, "paid_thinking": False, "strategy_audit_days": 10})
    monkeypatch.setattr(costmode, "may_spend", lambda usd: True)
    assert costmode.may_spend_on("text", 0.02) is False        # strategy = free only
    assert costmode.may_spend_on("strategy", 0.02) is False
    assert costmode.may_spend_on("grading", 0.02) is False
    assert costmode.may_spend_on("image", 0.10) is True        # art = paid allowed
    assert costmode.may_spend_on("video", 0.30) is True
    assert costmode.may_spend_on("voice", 0.01) is True

def test_audit_override_is_the_only_paid_thinking(monkeypatch):
    monkeypatch.setattr(costmode, "policy",
                        lambda: {"paid_art": True, "paid_thinking": False, "strategy_audit_days": 10})
    monkeypatch.setattr(costmode, "may_spend", lambda usd: True)
    assert costmode.may_spend_on("strategy", 0.05, override=True) is True

def test_free_only_beats_policy(monkeypatch):
    monkeypatch.setattr(costmode, "policy",
                        lambda: {"paid_art": True, "paid_thinking": True})
    monkeypatch.setattr(costmode, "may_spend", lambda usd: False)   # free_only / budget gone
    assert costmode.may_spend_on("image", 0.10) is False
