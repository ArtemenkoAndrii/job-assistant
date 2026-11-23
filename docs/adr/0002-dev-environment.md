# ADR-0002: Development environment and Claude Code isolation

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-23 |
| **Issue** | #9 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

Agents write most of the code and run commands on the developer's machine, a Windows laptop. They read untrusted content (vacancy texts, web pages), so a mistake or a prompt injection must not reach the laptop's files, other projects or cloud credentials. The project language is not chosen yet, so the environment must not depend on it. Claude Code's built-in sandbox runs on Linux and WSL2, not on native Windows.

## Decision drivers

- Isolation from the host: files, credentials, other projects (NFR-S2, NFR-S8).
- Restricted network egress for agents (prompt-injection blast radius, NFR-S6).
- Reproducible and versioned: the same environment on any machine, in Codespaces and in CI.
- Language-agnostic: toolchains are added when the stack is chosen.
- Low setup effort for one developer on Windows.

## Options considered

### Option 1: Claude Code natively on Windows

- Good: zero setup.
- Bad: no sandbox (not supported on native Windows); the agent sees the whole user profile; no egress control. Rejected.

### Option 2: WSL2 distribution only

- Good: Linux tools, Claude Code sandbox works.
- Bad: by default the Windows drive is mounted with write access and Windows binaries can be started (interop); hardening is manual and not versioned with the repo; no egress firewall.

### Option 3: Dev container on Docker Desktop (chosen)

The [Dev Containers specification](https://containers.dev) — `.devcontainer/` in the repo — opened by an IDE on Docker Desktop (which itself runs on WSL2).

- Good: the container is the isolation boundary; versioned with the repo; works in VS Code, JetBrains IDEs, GitHub Codespaces and the `devcontainer` CLI; based on Anthropic's reference Claude Code container with a default-deny egress firewall.
- Bad: Docker Desktop is required; bind-mounting a Windows folder is slow (mitigated by cloning into a container volume); the sandbox inside an unprivileged container needs the weaker nested mode.

### Option 4: Dev container on Docker Engine inside its own WSL distribution

- Good: no Docker Desktop.
- Bad: more manual setup (distribution, Docker Engine, code location); same container config as option 3, so it can be adopted later without changes.

## Decision

**Option 3.** Development happens in a dev container defined in `.devcontainer/`, run on Docker Desktop. The configuration is IDE-agnostic; any IDE that supports the Dev Containers specification can be used (VS Code has the most mature support).

The container provides three layers:

1. **Container** — the boundary: the agent sees only the repository and the container's own files. **No host folders and no cloud credentials are mounted** (no `~/.config/gcloud`, no Terraform credentials, no A-1 token). Cloud changes go through CI (Workload Identity Federation, ADR for #16).
2. **Egress firewall** (`init-firewall.sh`, from Anthropic's reference container): default deny; allowed only DNS, SSH, GitHub, the Docker host network and the domains in `.devcontainer/allowed-domains.txt` (Anthropic, OpenAI, npm, PyPI, VS Code). Adding a domain is a reviewed change.
3. **Claude Code sandbox** — enabled with `failIfUnavailable: true` through container-level user settings (`claude-settings.json`, merged into `$CLAUDE_CONFIG_DIR/settings.json` on container creation), so Claude Code refuses to start without it. `enableWeakerNestedSandbox: true` is required because bubblewrap cannot mount a fresh `/proc` in an unprivileged container; this is acceptable because the container is the primary boundary.

Recommended setup on Windows: Docker Desktop + an IDE with Dev Containers support + **"Clone repository in container volume"**, so the code lives in a Linux volume, not on the Windows drive (performance and isolation). Setup steps: [docs/dev-environment.md](../dev-environment.md).

Out of scope: runtime isolation of the product itself (A-1 and cloud), and language toolchains (added with the stack decision).

## Consequences

- Positive: agents work inside a reproducible, versioned boundary with restricted network; the same config serves Codespaces and later CI.
- Negative: Docker Desktop on the laptop; first build takes a few minutes; IP-based firewall rules are resolved at container start, so a service that changes IPs needs a container restart.
- Negative: spike kits that need the Browser MCP endpoint (A-1) cannot run in the container (its host is not in the allowlist, on purpose); they keep running outside, as before.
- Follow-ups: language toolchains and Terraform CLI when the stack and IaC ADRs are accepted; project-level `.claude/settings.json`, hooks and `CLAUDE.md` in #10 and #13.
