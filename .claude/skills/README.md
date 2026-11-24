# Project skills

Skills are instructions Claude Code loads when a task matches their `description`. Skills are advisory: rules that must always hold also need a hook, a CI check or a review pass (`REVIEW.md`).

| Skill | Kind | Triggers on |
|---|---|---|
| [writing-specs](writing-specs/SKILL.md) | Process | Writing or updating `spec.md` / `intent.md` |
| [security-privacy](security-privacy/SKILL.md) | Policy | Inputs, data, LLM calls, agent tools, auth, secrets, logs, browser, fixtures |
| [mobile-first-ux](mobile-first-ux/SKILL.md) | Policy | Any screen, component or email the user sees |
| [cost-guard](cost-guard/SKILL.md) | Policy | LLM calls, prompts, models, agent tasks, browsing volume, cloud resources |
| [resume-rules](resume-rules/SKILL.md) | Policy | Tailoring, added skills, answers, cover notes, reviewer agent |

Changes to policy skills are reviewed by the owner (they encode vision and NFR decisions).

## Trigger check

Run in the dev container, in a fresh `claude` session per prompt, from the repo root. A skill has triggered when Claude Code reports loading it (or uses its checklist in the answer). Write the result into the table of the PR that changes a skill.

| # | Prompt | Should trigger | Should not trigger |
|---|---|---|---|
| 1 | "Draft spec.md for issue #26 (search profile management) in docs/changes/26-search-profiles. Don't write code." | writing-specs, security-privacy, mobile-first-ux, cost-guard | resume-rules |
| 2 | "Draft spec.md for issue #29 (tailored resume generation)." | writing-specs, resume-rules, cost-guard, security-privacy | — |
| 3 | "What should the package page look like on a phone?" | mobile-first-ux | resume-rules |
| 4 | "We want to switch the review step to a bigger model. What does it cost?" | cost-guard | mobile-first-ux |
| 5 | "Fix the typo in README.md." | — | all five |

If a skill does not trigger, sharpen its `description` (what the task looks like, which files) rather than adding instructions to `CLAUDE.md`.
