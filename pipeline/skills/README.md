# Agent Skills

Each folder = one department's expert playbook, injected into that
department's LLM prompts at runtime (loader: `pipeline/agentcore/skills.py`).

## Adding a public skill from GitHub
1. Find a well-rated SKILL.md (Anthropic's `anthropics/skills` repo or any
   "awesome-claude-skills" list). Check the license — MIT/Apache are fine.
2. Trim it to the essentials (loader hard-caps at 3,500 chars — tokens cost money).
3. Save as `pipeline/skills/<department>/SKILL.md` and push. It loads on next boot.

Departments that read skills today: creative, cqo, editorial, research.
To give a new department a skill, create its folder here and call
`skills.skill_block("<dept>")` inside that department's prompt build.

## v5.8.3 — scouted skill sources
Distilled (not copied) from these open-source repos, all MIT/Apache-2.0,
adapted and trimmed for prompt injection:
- coreyhaines31/marketingskills (MIT) — social, copywriting, analytics, seo
- charlie947/social-media-skills (MIT) — hook-generator, post-scorer, niche-research
- boraoztunc/skills (Apache-2.0) — ogilvy copywriting principles
- OpenClaudia/openclaudia-skills (MIT) — surveyed for content/repurposing ideas
Departments now carrying skills: creative, cqo, editorial, research,
distribution, brand_studio, community, analytics.
