# Job Finder

AI assistant that finds vacancies on LinkedIn and Glassdoor, researches employers and prepares a tailored application package for each matching vacancy — resume, employer dossier, answers to typical questions and the link to apply. The user applies manually.

The project is also a practice ground for building a product as an AI factory, following Anthropic's [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook).

## Documentation

- [Vision](docs/vision.md)
- [Use cases](docs/requirements/use-cases.md) and [non-functional requirements](docs/requirements/nfr.md)
- [Architecture](docs/architecture.md) (draft) and [architecture decisions](docs/adr/README.md)
- [Development environment](docs/dev-environment.md)
- [How changes are made](docs/changes/README.md) · [Review guide](REVIEW.md) · [Agent guide](CLAUDE.md)

## Repository layout

| Path | Contents |
|---|---|
| `docs/` | Vision, requirements, ADRs, change artifacts, templates, spike findings |
| `spikes/` | Throwaway feasibility kits |
| `.devcontainer/` | Dev container with egress firewall and Claude Code sandbox |
| `.claude/` | Claude Code project settings, skills, `verifier` subagent, guard hooks |
| `.github/` | CI workflow and the `main` ruleset |
| `apps/jobfinder/` | The application (Python, [ADR-0005](docs/adr/0005-application-stack.md)) |
| `scripts/`, `tests/` | `build.sh`, `lint.sh`, `test.sh`, `audit.sh` and the hook tests |

Planned, created by their issues: `infra/` (Terraform, #16), `evals/` (datasets and eval suite, #24–#25).

## Status

Roadmap and progress: GitHub milestones P0–P5 and issues.
