"""v5.11.23 (DEC-076) — sticky chrome, account pipeline tab, lessons loop,
Railway MCP tools. Source-level assertions: cheap, no network, and they fail
loudly if a future refactor silently drops a wire."""
import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


# ── REQ-STICKY-CHROME ────────────────────────────────────────────────────
def test_banner_is_sticky():
    s = _read("web/components/VersionBanner.tsx")
    assert 'className="vbanner"' in s
    assert '"sticky"' in s and "zIndex: 60" in s


def test_css_offsets_follow_banner():
    s = _read("web/app/globals.css")
    assert "body:has(.vbanner) header.site" in s
    assert "body:has(.vbanner) .wrap.shell > .sidebar" in s
    # mobile: banner must give the space back
    assert ".vbanner { position: static !important; }" in s


# ── REQ-ACCOUNT-PIPELINE ─────────────────────────────────────────────────
def test_pipeline_route_exists_and_is_cas_guarded():
    s = _read("web/app/api/projects/[pid]/accounts/[aid]/pipeline/route.ts")
    assert "verifyOwnership" in s
    assert '.eq("account_id", params.aid)' in s
    assert '.eq("status", "drafted")' in s          # CAS transition guard
    assert '"item not in this account"' in s        # cross-account block


def test_account_page_has_live_content_tab():
    s = _read("web/app/dashboard/projects/[pid]/accounts/[aid]/page.tsx")
    assert '"pipeline",  label:"Live content"' in s.replace("key:", "").replace("{ ", "") or \
           'key:"pipeline"' in s
    assert "function PipelineTab" in s
    assert "/pipeline`" in s


# ── REQ-LESSONS-LOOP ─────────────────────────────────────────────────────
def test_lessons_for_exists_and_fails_open():
    s = _read("pipeline/workers/common.py")
    assert "def lessons_for(" in s
    assert 'status", "rejected"' in s.replace("(", '"').replace("'", '"') or \
           '.eq("status", "rejected")' in s
    assert 'return ""' in s  # fail-open contract


def test_lessons_wired_into_both_writers():
    s = _read("pipeline/workers/departments/creative.py")
    assert s.count("lessons_for") >= 2          # write_script + write_carousel
    assert "_lessons" in s
    # write_script rides the grade_feedback channel
    assert "grade_feedback=_fb" in s


# ── REQ-RAILWAY-MCP ──────────────────────────────────────────────────────
def test_railway_tools_registered_and_readonly():
    s = _read("web/app/api/mcp/route.ts")
    assert '"agentx_railway_status"' in s and '"agentx_railway_logs"' in s
    assert "Project-Access-Token" in s
    assert "RAILWAY_PROJECT_TOKEN" in s
    # read-only contract: no mutation verbs in the railway section
    seg = s[s.find("Railway (v5.11.23"):]
    for verb in ("deploymentRestart", "serviceInstanceRedeploy", "mutation"):
        assert verb not in seg, f"railway tools must stay read-only ({verb} found)"
