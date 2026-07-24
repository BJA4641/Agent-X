"""v5.11.24 (DEC-077) — workbook system, per-agent playbooks, reel titles,
prep visibility. Source-level, no network."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ── REQ-WORKBOOK ─────────────────────────────────────────────────────────
def test_playbooks_module_shape():
    from agentcore.playbooks import PLAYBOOKS, get_playbook
    for role in ("writer", "carousel_writer", "strategist", "qa"):
        assert role in PLAYBOOKS and len(PLAYBOOKS[role]) > 80
        assert get_playbook(role).endswith("\n")
    assert get_playbook("nonexistent") == ""       # always-safe contract
    # token discipline: playbooks must stay short
    for role, text in PLAYBOOKS.items():
        assert len(text.split()) <= 160, f"{role} playbook too long"


def test_workbook_in_brand_studio_docs():
    s = _read("pipeline/workers/departments/brand_studio.py")
    assert '"workbook",' in s                       # REQUIRED_DOCS entry
    assert '"workbook": (' in s                     # niche default exists


def test_workbook_and_playbook_reach_writers():
    b = _read("pipeline/agent/brain.py")
    assert 'get_playbook' in b and '_wb' in b
    assert 'brand["content_rules"]' in b            # rides existing channel
    c = _read("pipeline/workers/departments/creative.py")
    assert 'get_playbook' in c and '_wb_line' in c  # carousel prompt


def test_qa_playbook_leads_grounding():
    s = _read("pipeline/agent/qa.py")
    assert 'get_playbook' in s and '_pb("qa")' in s


# ── REQ-REEL-TITLES ──────────────────────────────────────────────────────
def test_reels_take_writer_title_first_draft_only():
    s = _read("pipeline/workers/departments/creative.py")
    assert "REQ-REEL-TITLES" in s
    assert "if rewrite == 0:" in s                  # never clobber human edits
    assert '8 <= len(gen_title) <= 110' in s


# ── REQ-PREP-VISIBILITY ──────────────────────────────────────────────────
def test_prep_items_visible_in_account_pipeline():
    s = _read("web/app/api/projects/[pid]/accounts/[aid]/pipeline/route.ts")
    assert '"prep"' in s


# ── strategist niche rule reached the one LLM call ───────────────────────
def test_angle_rewrite_enforces_niche_nativeness():
    s = _read("pipeline/workers/departments/editorial.py")
    assert "NATIVE to the niche" in s
