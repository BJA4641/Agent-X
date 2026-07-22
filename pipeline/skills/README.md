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
