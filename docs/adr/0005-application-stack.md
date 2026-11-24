# ADR-0005: Application stack

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-24 |
| **Issue** | #46 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

[ADR-0004](0004-agent-runtime.md) fixed the agent runtime: Pydantic AI with OpenAI, the agent loop in the worker, `BrowserGateway` over one MCP session. The owner chose **Python** for the product code (decided with ADR-0004, so the language is not compared again here): it is the language they review most comfortably, and it has the richest agent and MCP libraries.

Still open: Python version, packaging, web framework and UI approach, libraries for PDFs, the tools behind `lint`, `test` and `build`, the layout of `apps/`, and the toolchain in the dev container. The [architecture](../architecture.md) has two runtime parts — a web app and a long-running worker — that share the domain model, the LLM gateway and storage access.

Hosting (#15), storage (#18) and sign-in (#17) are not decided yet; this ADR must not lock them in.

## Decision drivers

- **AI-agent friendliness:** mainstream, well documented, typed, quick to test — agents write most of the code, the owner reviews it.
- **Simplicity** for one part-time developer: one language, no front-end build step, few moving parts (CLAUDE.md).
- **Mobile-first UI** without a separate front-end project: 360 px, one-tap actions, WCAG 2.2 AA (NFR-U1–U4).
- **Fits ADR-0004:** async Python, Pydantic models end to end.
- **Portable to the free tier** of any cloud: one container image, no platform-specific framework (#15).
- **One command each** for build, test and lint, non-zero on failure (NFR-M4); dependency scan in CI (NFR-S7).
- Licences compatible with a public repository (no AGPL in the product).

## Options considered

### Web framework and UI

**W1. FastAPI + server-rendered Jinja2 templates + htmx.** Pages are HTML from the server; htmx swaps fragments for interactive parts (upload preview, reject a skill, mark applied).
- Good: one language; no JavaScript build; Pydantic models shared with the pipeline; async fits Pydantic AI; FastAPI, Jinja2 and htmx are very well known to coding agents.
- Bad: auth, sessions, CSRF and admin are assembled from small pieces rather than built in.

**W2. Django (+ htmx).**
- Good: auth, ORM, migrations, admin and CSRF built in.
- Bad: the ORM assumes a relational database, which may not be the free-tier choice (#18); sync-first; two model systems (Django models and Pydantic).

**W3. FastAPI JSON API + single-page app (React/TypeScript).**
- Good: rich interactions.
- Bad: a second language, toolchain and build; twice the surface for agents and reviews; the MVP UI is forms and tables.

### Package and environment management

**P1. uv** (project, lock file, Python install, tool runner) vs **P2. pip + venv + pip-tools** vs **P3. Poetry**. uv is one fast tool for all of it, with a lock file and Python version management; pip-tools needs several tools; Poetry is slower and does not manage Python versions.

### MCP client (inside `BrowserGateway`)

**M1. Official `mcp` Python SDK** (`ClientSession` over Streamable HTTP) vs **M2. FastMCP client** (higher-level, the one Pydantic AI's `MCPToolset` wraps) vs **M3. Pydantic AI `MCPToolset`** handed to the agent directly. M3 would let the model call A-1 without our checks, against ADR-0004. M1 and M2 both work; M1 is the reference implementation, follows the protocol revisions first and gives the gateway direct control of the session and headers.

### Type checking

**T1. Pyright** (mature, fast, strict mode; Pydantic support) vs **T2. mypy** (slower; plugin for Pydantic) vs **T3. ty** (Astral's checker, very fast, but still 0.0.x with breaking changes between versions).

## Decision

**W1 + P1 + T1**, with these versions and libraries:

| Area | Choice | Why |
|---|---|---|
| Language | **Python 3.14** | Mature for a year; 3.15 (released 9 Oct 2026) is adopted once our dependencies ship wheels for it |
| Packages, Python, lock | **uv**, `uv.lock` committed | One tool; `uv sync --locked` reproduces the environment in the dev container, CI and the image |
| Web | **FastAPI** + **Jinja2** templates + **htmx 2** | Server-rendered, no JS build. htmx 2 rather than 4: v4 (Aug 2026) changed defaults such as attribute inheritance, and agents know v2 far better; v2 stays supported. Revisit later |
| CSS | **Pico CSS**, vendored | Classless, responsive and accessible by default; no build step |
| Agents and LLM | **Pydantic AI** (`pydantic-ai-slim[openai]`) | ADR-0004 |
| MCP client | official **`mcp`** SDK, used only inside `BrowserGateway` | M1 above |
| Validation and settings | **Pydantic**, **pydantic-settings** | Same models in web, worker and agents |
| HTTP client | **httpx** | Async; used by the SDKs above |
| PDF out (tailored resume) | **WeasyPrint** (HTML/CSS → PDF) | Text-selectable PDF from the same templates; BSD licence (NFR-F4) |
| PDF in (uploads) | **pypdf** | Text extraction, BSD licence; PyMuPDF rejected (AGPL) |
| Database access | decided in #18 | Kept behind a repository interface in `storage/` |
| Lint and format | **Ruff** (`ruff check`, `ruff format --check`) | One fast tool, wide rule set |
| Types | **Pyright** (standard mode; strict for `browser/`, `llm/`, `pipeline/`) | Strict where the safety-critical code is |
| Tests | **pytest**, **pytest-asyncio**, Pydantic AI `TestModel`/`FunctionModel`, **respx** for HTTP fakes | No test calls OpenAI or A-1 (NFR-M5) |
| Dependency scan | **pip-audit** on the locked requirements, a separate CI step (`scripts/audit.sh`, needs network) | NFR-S7. pip-audit has no severity filter, so any known vulnerability fails — stricter than NFR-S7; a finding that does not apply is ignored by ID with a reason in the file |
| UI checks | **Playwright for Python** (headless Chromium) for screenshots at 360/768/1280 px and **axe-core** accessibility checks against the local app; **Lighthouse** in CI | NFR-U1, U3, U4; added with the first UI slice (#22/#26), tests only `localhost` |
| Runtime packaging | **one container image**, two entry points: web (`uvicorn`) and worker (`python -m jobfinder.worker`) | Portable to any free tier; the platform is chosen in #15 |

**Layout** — one application in `apps/`, one Python package with one folder per architecture component:

```
apps/jobfinder/
  pyproject.toml, uv.lock, Dockerfile
  src/jobfinder/
    domain/      models: profile, run, vacancy, dossier, package, registry
    pipeline/    orchestrator and steps (UC-07)
    browser/     BrowserGateway, MCP client, stop detection
    llm/         LLM gateway: model registry, cost ledger, budget guard
    storage/     repositories (implementation after #18)
    web/         FastAPI app, templates, static (htmx, Pico)
    worker/      entry point: take a run from the queue, execute it
    config.py    settings from environment and the secret manager
  tests/         unit/ (fast, no network), integration/ (fake MCP, recorded LLM responses)
```

A second app (e.g. the fake MCP server for #24) gets its own folder in `apps/` when it is needed.

**Commands** (CLAUDE.md, CI):

| Command | Runs |
|---|---|
| `scripts/build.sh` | `uv sync --locked`, then `uv build` for `apps/jobfinder` (the container image is built by CI/deploy, #16) |
| `scripts/lint.sh` | existing repo checks + `ruff check`, `ruff format --check`, `pyright` (offline) |
| `scripts/audit.sh` | `pip-audit` (online; CI step) |
| `scripts/test.sh` | hook tests + `pytest` |

**Dev container:** at image build, before the firewall exists: uv (pinned, from PyPI), Python 3.14 **installed by uv** (not Debian's `python3`), WeasyPrint's system libraries (Pango), and later Playwright's Chromium. At run time `UV_PYTHON_DOWNLOADS=never`, so nothing needs GitHub release downloads; `uv sync` uses PyPI, which is already allowed. No new domains in the firewall.

Out of scope: hosting platform (#15), database and file storage (#18), sign-in (#17), email (#21).

## Consequences

- Positive: one language and one image for everything; agents work with mainstream, typed libraries; tests run offline.
- Positive: the UI needs no JavaScript build; pages work on a phone by default with Pico and server rendering.
- Negative: sign-in, sessions and CSRF are assembled rather than built in — addressed in #17.
- Negative: WeasyPrint pulls in system libraries, which makes the image larger (tens of MB) and may slow a scale-to-zero cold start (NFR-A1 allows ≤ 10 s); #15 checks this, and the web and worker images can be split later if needed.
- Negative: htmx 2 and Python 3.14 are one major version behind; upgrades are planned, not urgent.
- Done with this ADR: Python toolchain in the dev container; `apps/jobfinder` skeleton with one passing test; `build.sh`, `lint.sh`, `test.sh`, `audit.sh` and CI updated; CLAUDE.md commands and ADR index; [architecture](../architecture.md) Q1 and §2 note.
- Follow-ups (other issues): #15 picks a platform that runs the image as a web service and as a 90-minute job; #18 decides the database and the repository implementation; #22 builds on this skeleton.
