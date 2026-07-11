# dev-skills

Personal Codex skills catalog, mirrored from the custom skills installed in
`~/.codex/skills`. Built-in `.system` skills are intentionally excluded.

## Skills

| Skill | Description |
| --- | --- |
| [`aliyun-deploy`](skills/.curated/aliyun-deploy) | Aliyun ECS container deployment and troubleshooting. |
| [`commit`](skills/.curated/commit) | Commit completed work and clean up confirmed AI-owned Git leftovers. |
| [`development`](skills/.curated/development) | Unified workflow for software development and related documentation changes. |
| [`development-plan`](skills/.curated/development-plan) | Planning and progress tracking for complex development work. |
| [`merge-pr`](skills/.curated/merge-pr) | Review or merge an existing GitHub pull request or GitLab merge request. |
| [`resolve-issue`](skills/.curated/resolve-issue) | Deliver a fix or feature starting from a GitHub or GitLab issue. |
| [`skill-retrospective`](skills/.curated/skill-retrospective) | Improve skills or `AGENTS.md` using evidence from repeated agent failures. |

## Install

Install one skill with Codex's built-in skill installer:

```bash
python ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo zane98/dev-skills \
  --path skills/.curated/<skill-name>
```

Restart Codex after installation so the new skill is discovered.
