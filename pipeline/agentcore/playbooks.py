"""agentcore/playbooks.py — v5.11.24 REQ-WORKBOOK (DEC-077).

Per-AGENT operating guides, injected into each agent's prompt at its call
site. This is the founder's "workbook" idea made concrete and honest: agents
don't magically gain skills — they follow written procedure, and procedure
lives HERE (per role) plus in the per-ACCOUNT `workbook` document that
brand_studio generates (niche-specific rules, editable by the owner in the
account page → 📖 Workbook tab).

Design constraints:
- SHORT. Every word here is paid for on every single call. Target ≤120 words
  per role. If a rule doesn't change output, it doesn't belong here.
- Rules must be checkable. "Be creative" is noise; "title must describe the
  content itself, never the source trend's caption" is a rule the QA gate and
  a human can verify.
- One source of truth: if a rule graduates into code (like title guards did),
  DELETE it here — code beats prose.
"""

PLAYBOOKS = {
    "writer": (
        "WRITER PLAYBOOK: 1) Hook names a specific pain/outcome in ≤12 words — "
        "no clickbait you can't cash. 2) Every beat is one concrete, doable "
        "idea; cut any beat that is 'why this matters' filler. 3) Title must "
        "describe THIS content, never echo a trend's caption. 4) CTA asks one "
        "small action (save/comment keyword), never 'follow for more' alone. "
        "5) No income claims, no medical claims, no 'guaranteed'. 6) Apply the "
        "account WORKBOOK and LESSONS blocks above everything else — a lesson "
        "violated is an automatic rejection."
    ),
    "carousel_writer": (
        "CAROUSEL PLAYBOOK: 1) Slide 1 = the promise in ≤8 words, readable at "
        "thumbnail size. 2) One idea per slide; a slide that needs two "
        "sentences is two slides. 3) Slides 2..N-1 each advance a numbered "
        "method — no restating the hook. 4) Last slide = CTA + the promise "
        "kept. 5) Title = slide 1's promise, never the source trend caption. "
        "6) WORKBOOK and LESSONS blocks override style preferences."
    ),
    "strategist": (
        "STRATEGIST PLAYBOOK: 1) Only adopt a trend if it maps to this "
        "account's niche after adaptation — a spa trend can inspire a puppy "
        "bedtime post, but the RESULT must read native to the niche. 2) Never "
        "repeat a topic in the recent-topics list. 3) Prefer topics with a "
        "clear actionable payoff over vibes. 4) One format per idea (reel OR "
        "carousel), chosen by what the payoff needs: steps → carousel, "
        "demonstration/emotion → reel."
    ),
    "qa": (
        "QA PLAYBOOK: Reject, with a one-line reason the writer can act on, "
        "if ANY of: hook is generic ('you won't believe'), title doesn't "
        "match content, any beat is filler, CTA is bare 'follow', claim is "
        "unverifiable or forbidden (income/medical/guarantee), or a LESSONS "
        "rule is violated. Pass = specific, native to niche, promise kept. "
        "Grade the content in front of you, not the topic's potential."
    ),
}


def get_playbook(role: str) -> str:
    """Return the playbook block for a role, or "" — always safe to inject."""
    p = PLAYBOOKS.get(str(role or "").strip().lower())
    return (p + "\n") if p else ""
