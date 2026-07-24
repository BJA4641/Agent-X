"""v5.11.22 regression tests — REQ-TOPIC-MEMORY, REQ-CAROUSEL-TITLES,
REQ-IMG-ASPECT, REQ-IMG-REALISM (DEC-075).

Source-level assertions: cheap, no network, no Supabase — they lock the fix
shapes in place so a future refactor cannot silently reintroduce the
2026-07-24 "55 identical carousels, stretched AI-looking slides" incident.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EDI = (ROOT / "workers/departments/editorial.py").read_text()
CRE = (ROOT / "workers/departments/creative.py").read_text()
VIS = (ROOT / "agent/visuals.py").read_text()
PRE = (ROOT / "preflight.py").read_text()


# ---- REQ-TOPIC-MEMORY --------------------------------------------------------
def test_topics_recent_helper_exists():
    assert "def _topics_recent(" in EDI
    assert '"board_items"' in EDI.split("def _topics_recent(")[1][:900]

def test_topics_recent_fails_open():
    body = EDI.split("def _topics_recent(")[1].split("def _pick_topics(")[0]
    assert "return set()" in body and "except Exception" in body

def test_pick_topics_accepts_avoid():
    assert "def _pick_topics(n: int, account=None, account_id=None, avoid: set = None)" in EDI
    assert "seen: set = set(avoid or ())" in EDI

def test_all_three_planners_pass_avoid():
    assert EDI.count("avoid=_topics_recent(sb, account_id)") == 3

def test_trend_angled_form_checked_against_memory():
    # both trend passes must re-check the ANGLED candidate, not just the raw title
    assert EDI.count("if cand.lower() in seen") == 2


# ---- REQ-CAROUSEL-TITLES -----------------------------------------------------
def test_write_carousel_retitles_from_generated_title():
    seg = CRE.split("def write_carousel(")[1].split("def _slide_card(")[0]
    assert 'data.get("title")' in seg
    assert '{"topic": f"[carousel] {gen_title}"' in seg

def test_retitle_is_guarded():
    seg = CRE.split("def write_carousel(")[1].split("def _slide_card(")[0]
    assert "8 <= len(gen_title) <= 110" in seg  # no empty/garbage titles
    assert seg.count("except Exception") >= 2   # retitle failure never kills the job


# ---- REQ-IMG-ASPECT ----------------------------------------------------------
def test_slide_card_uses_aspect_preserving_fit():
    seg = CRE.split("def _slide_card(")[1].split("def render_carousel(")[0]
    assert "_IO.fit(" in seg and "(1080, 1350)" in seg

def test_slide_card_stretch_removed():
    seg = CRE.split("def _slide_card(")[1].split("def render_carousel(")[0]
    assert 'resize((1080, 1920))' not in seg


# ---- REQ-IMG-REALISM ---------------------------------------------------------
def test_realistic_styles_defined():
    assert "REALISTIC_STYLES" in VIS
    for name in ("real-daylight", "real-ugc"):
        assert f'"{name}"' in VIS

def test_realism_prompts_carry_negatives():
    assert "no CGI" in VIS and "no illustration" in VIS

def test_pick_style_pool_param():
    assert "def pick_style(item_id, override: str = None, pool: str = None)" in VIS
    assert 'pool == "realistic"' in VIS

def test_render_carousel_uses_realistic_pool():
    seg = CRE.split("def render_carousel(")[1]
    assert 'pick_style(item_id, pool="realistic")' in seg
    assert "except TypeError" in seg  # graceful on older visuals.py


# ---- preflight guard ---------------------------------------------------------
def test_preflight_lists_new_symbols():
    assert '"_topics_recent", "v5.11.22"' in PRE
    assert '"REALISTIC_STYLES", "v5.11.22"' in PRE
