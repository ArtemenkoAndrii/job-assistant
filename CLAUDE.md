# Job Finder — agent guide

AI assistant that finds vacancies on LinkedIn and Glassdoor, researches employers and prepares an application package per vacancy; the user applies manually. Start with [docs/vision.md](docs/vision.md).

## Where things are

| Path | What |
|---|---|
| `docs/vision.md` | Product vision — scope, principles, constraints |
| `docs/requirements/` | Use cases (UC-NN) and non-functional requirements (NFR-XN) |
| `docs/architecture.md` | System context, containers, components, run sequence, deployment, decision log, open items |
| `docs/adr/` | Architecture decisions — read the index before designing anything |
| `docs/changes/<issue>-<slug>/` | intent.md, spec.md, plan.md per change ([how](docs/changes/README.md)) |
| `docs/templates/` | Templates for intent, spec, plan |
| `.claude/skills/` | Spec-writing process and policy skills (security, cost, mobile UX, resume rules) |
| `.claude/agents/`, `.claude/hooks/` | `verifier` subagent; guard hooks (no push to `main`, no secrets) — see `.claude/settings.json` |
| `apps/jobfinder/` | The application: `src/jobfinder/{domain,pipeline,browser,llm,notify,storage,web,worker}`, `tests/`, `Dockerfile` ([ADR-0005](docs/adr/0005-application-stack.md)) |
| `infra/`, `docs/runbooks/` | Terraform layers `platform` (owner) and `app` (CI), and the owner's bootstrap runbook ([ADR-0009](docs/adr/0009-infrastructure-as-code.md)) |
| `scripts/`, `tests/` | Build, lint, test and audit entry points; tests for the hooks |
| `docs/spikes/`, `spikes/` | Feasibility findings and throwaway spike kits — not product code |
| `.devcontainer/` | The only supported dev environment ([ADR-0002](docs/adr/0002-dev-environment.md)) |

## Commands

| Command | What |
|---|---|
| `scripts/build.sh` | `uv sync --locked` and `uv build` for `apps/jobfinder` |
| `scripts/lint.sh` | shellcheck, JSON, Markdown links, A-1 references, no Proposed ADRs, infra rules (no `pull_request_target`, no `allUsers`, Terraform pin), `terraform fmt`, Ruff, Pyright, gitleaks (offline) |
| `scripts/test.sh` | Hook tests, script tests and `pytest` (no network: fake models and fake MCP only) |
| `scripts/audit.sh` | pip-audit of locked dependencies (needs network; CI step) |

CI runs all four on every PR, then builds the container image and smoke-tests it (`.github/workflows/ci.yml`). Each command exits non-zero on failure. Add dependencies with `uv add` inside `apps/jobfinder`; commit `uv.lock`.

## Workflow

1. Work starts from a GitHub issue; branch from the latest `main`, name `<issue>-<short-slug>`, keep it short-lived ([ADR-0003](docs/adr/0003-branching-strategy.md)).
2. Product changes go **intent → spec → plan → code**. Specs follow the `writing-specs` skill. Plan in plan mode first; do not write code before the plan is approved. Plan mode is read-only: right after approval, the first commit saves the approved plan as `docs/changes/<issue>-<slug>/plan.md` (from `docs/templates/plan.md`); code comes after.
3. Open a PR with `Closes #N`; the owner reviews and squash-merges. Never push to `main` (a ruleset blocks it). To update a branch, merge `main` into it; never force-push a branch under review.
4. If the implementation diverges from `plan.md`, update it in the same commit.

## Accepted decisions (ADR index)

- ADR-0001 Record architecture decisions
- ADR-0002 Development environment and Claude Code isolation
- ADR-0003 Branching strategy
- ADR-0004 Agent runtime and LLM provider (Pydantic AI, OpenAI, loop in the worker)
- ADR-0005 Application stack (Python 3.14, uv, FastAPI + Jinja2 + htmx, one image)
- ADR-0006 Hosting (GCP `job-finder` project, us-central1, Cloud Run service + job, Scheduler)
- ADR-0007 Data and file storage (Firestore + private Cloud Storage bucket, TTL retention, run lease)
- ADR-0008 User authentication (IAP on Cloud Run, app verifies the IAP JWT and the owner email)
- ADR-0009 Infrastructure as code (Terraform; `infra/platform` applied by the owner, `infra/app` by CI via WIF)
- ADR-0010 Notifications and email delivery (channels behind `Notifier`; email via a dedicated Gmail, Gmail API `gmail.send`, Personal mode)
- ADR-0011 Browser automation policy (gateway tool/URL/click allowlists, no JavaScript or typing, limits, stop triggers per board)
- ADR-0012 Deployer's Cloud Run IAM-policy right at project level (supersedes that scope in ADR-0009)

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
- ADRs were merged while still Proposed (ADR-0003, ADR-0007). Ask the owner to accept before merge and set Accepted + indexes in the same PR; `scripts/lint.sh` now fails while an ADR is Proposed (#59).
