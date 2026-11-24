# Job Finder — agent guide

AI assistant that finds vacancies on LinkedIn and Glassdoor, researches employers and prepares an application package per vacancy; the user applies manually. Start with [docs/vision.md](docs/vision.md).

## Where things are

| Path | What |
|---|---|
| `docs/vision.md` | Product vision — scope, principles, constraints |
| `docs/requirements/` | Use cases (UC-NN) and non-functional requirements (NFR-XN) |
| `docs/adr/` | Architecture decisions — read the index before designing anything |
| `docs/changes/<issue>-<slug>/` | intent.md, spec.md, plan.md per change ([how](docs/changes/README.md)) |
| `docs/templates/` | Templates for intent, spec, plan |
| `.claude/skills/` | Spec-writing process and policy skills (security, cost, mobile UX, resume rules) |
| `.claude/agents/`, `.claude/hooks/` | `verifier` subagent; guard hooks (no push to `main`, no secrets) — see `.claude/settings.json` |
| `scripts/`, `tests/` | Lint and test entry points; tests for the hooks |
| `docs/spikes/`, `spikes/` | Feasibility findings and throwaway spike kits — not product code |
| `.devcontainer/` | The only supported dev environment ([ADR-0002](docs/adr/0002-dev-environment.md)) |

## Commands

| Command | What |
|---|---|
| `scripts/lint.sh` | shellcheck, JSON, Markdown links, A-1 references, gitleaks |
| `scripts/test.sh` | All tests (now: the guard hooks) |

CI runs both on every PR (`.github/workflows/ci.yml`). No product code yet: build and language-specific checks are added to these scripts with the stack decision (#46). Each stays one command that exits non-zero on failure.

## Workflow

1. Work starts from a GitHub issue; branch from the latest `main`, name `<issue>-<short-slug>`, keep it short-lived ([ADR-0003](docs/adr/0003-branching-strategy.md)).
2. Product changes go **intent → spec → plan → code**. Specs follow the `writing-specs` skill. Plan in plan mode first; do not write code before the plan is approved.
3. Open a PR with `Closes #N`; the owner reviews and squash-merges. Never push to `main` (a ruleset blocks it). To update a branch, merge `main` into it; never force-push a branch under review.
4. If the implementation diverges from `plan.md`, update it in the same commit.

## Accepted decisions (ADR index)

- ADR-0001 Record architecture decisions
- ADR-0002 Development environment and Claude Code isolation
- ADR-0003 Branching strategy

A spec must not contradict an accepted ADR; if it has to, stop and propose a new ADR.

## Rules

- **Hooks block** pushes to `main`, force-push, `--no-verify` and writing secrets. If a hook blocks you, fix the cause; never work around it.
- **Never touch real job boards** from tests, CI or the dev container: use recorded pages and fakes. The Browser MCP endpoint (A-1) is reachable only from runtime and spike kits.
- **The repo is public:** no secrets, no personal data (resumes, names, contacts, recorded pages with personal data). Secrets live in a secret manager.
- **Never invent experience** in anything that generates resumes; added skills follow vision §9.
- Browsing is **read only**: the product never fills or submits forms.
- Prefer the simplest thing that meets the spec; respect the budgets (NFR-C1, NFR-C2).

## Before reporting a task as done

- [ ] Build, tests and lint pass (paste the output).
- [ ] Every acceptance criterion in `spec.md` has evidence (see `plan.md` → Proof).
- [ ] `plan.md` matches what was built.
- [ ] No secrets or personal data in the diff.
- [ ] Docs touched by the change are updated (ADR index, use cases, NFR, README).
- [ ] The `verifier` subagent reports PASS (quote its verdict in the PR).

## Known mistakes

<!-- When an agent makes the same mistake twice, add the correction here. -->
- None yet.
