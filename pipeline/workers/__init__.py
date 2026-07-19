"""workers — v2 blueprint agents wired to the JobQueue/EventBus.

Departments are organized per the org chart (01-ORG-CHART.md):
  A  Portfolio Management     (portfolio_mgmt)
  B  Brand Studio             (brand_studio)    — onboarding/brand docs
  C  Editorial               (editorial)       — scout/research/strategy/planner
  D  Creative                (creative)        — brain/script/visuals/voice/composer
  E  Post-Production         (post)            — captions/overlays/SFX/music
  F  Distribution            (distribution)    — publisher, cross-platform
  G  Research
  H  Growth
  I  Monetization
  J  Analytics
  K  Finance                 (cfo)             — budget/kill switch
  L  Infrastructure
  M  Knowledge               (memory/lessons)
  N  Innovation
  O  Quality                 (cqo)             — grader/quality gate
  P  Risk                    (risk)            — claim/compliance

Phase 2 MVP wires the 35 core agents needed to autonomously produce and
publish content end-to-end for the single active brand (AI Tool Daily).
"""
