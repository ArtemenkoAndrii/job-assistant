# Development environment

Development happens in a dev container ([ADR-0002](adr/0002-dev-environment.md)). The container isolates agents from the laptop, restricts network egress and runs Claude Code with its sandbox enabled.

## One-time setup (Windows)

1. Install a **container runtime** that works with Dev Containers — any of Docker Desktop, Rancher Desktop, Podman Desktop, or Docker Engine in your own WSL distribution. (Or skip local setup and use GitHub Codespaces.)
2. Install an IDE with Dev Containers support:
   - **VS Code** + the *Dev Containers* extension (most mature), or
   - a **JetBrains IDE** with Dev Containers support.
3. Make sure git does not convert line endings for this repo (the repo's `.gitattributes` already forces LF for scripts).

## Open the project

**VS Code (recommended path):** Command Palette → **Dev Containers: Clone Repository in Container Volume…** → `https://github.com/ArtemenkoAndrii/job-assistant`.
The code then lives in a Linux volume, which is faster and keeps it off the Windows drive. (Opening a local Windows folder with *Reopen in Container* also works, but file access is slower.)

**JetBrains:** create a Dev Container from the repository URL in the IDE's remote development / Dev Containers dialog.

The first build takes a few minutes. When it is done, the terminal shows:

```
Claude Code settings: sandbox enabled, failIfUnavailable=true (...)
Git hooks: .githooks (gitleaks 8.21.2)
Firewall ready: default deny, N allowed domains + GitHub
```

## First run of Claude Code

In the container terminal:

```bash
claude
```

Log in when asked (the login is stored in a Docker volume and survives rebuilds). Then check:

- `/sandbox` — the sandbox is **enabled**; if Claude Code exits at start with a sandbox error, see Troubleshooting.
- `curl -sI https://example.com` fails, `curl -s https://api.github.com/zen` returns a short phrase — the firewall is active.

## Python

The container has **uv** and **Python 3.14** (installed by uv at build time). In `apps/jobfinder`: `uv sync` creates `.venv`; `uv add <package>` adds a dependency and updates `uv.lock`; `uv run pytest` runs the tests. From the repo root, `scripts/build.sh`, `scripts/lint.sh` and `scripts/test.sh` run everything; `scripts/audit.sh` checks dependencies for known vulnerabilities (needs PyPI). The Python version is in `apps/jobfinder/.python-version`; the dev container, CI and the image use the same one. uv cannot download Python versions at run time (`UV_PYTHON_DOWNLOADS=never`, firewall); a new Python version comes with a container rebuild.

## GitHub access for agents

Claude Code in the container uses `gh` and `git push` with its **own** token, not your personal login: a fine-grained personal access token that cannot change repository settings, so the `main` ruleset (ADR-0003) cannot be switched off from the container.

1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token.
2. Repository access: **Only select repositories** → `job-assistant`. Expiration: 90 days or less.
3. Repository permissions: **Contents**: Read and write · **Pull requests**: Read and write · **Issues**: Read and write · **Metadata**: Read (automatic). Leave everything else, especially **Administration** and **Workflows**, at *No access*.
4. In the container: `gh auth login` → GitHub.com → HTTPS → paste the token; then `gh auth setup-git`.

The token is stored in a container volume (`~/.config/gh`), not in the repo, and survives rebuilds. `gh` reads it inside the Claude Code sandbox. Hooks keep the agent's file tools (Read, Grep, Glob) out of `~/.config/gh`, including searches that start above it, and block the usual ways to print it from the shell (`gh auth token`, `gh auth status -t`, reading `~/.config/gh`); all of these checks are pattern-based and best effort, so the real limit is the token's narrow scope. Do not add a `Read(~/.config/gh/**)` deny rule: the sandbox applies Read deny rules to every command, and `gh` then looks logged out. To revoke, delete the token on GitHub. Without **Workflows** permission the agent cannot change `.github/workflows/`; such changes are pushed by you.

## Guardrails

| Guard | Where | What it stops |
|---|---|---|
| Ruleset on `main` | GitHub ([ADR-0003](adr/0003-branching-strategy.md)) | Any change to `main` without a PR and a green `ci` check |
| Claude Code hooks | `.claude/hooks/`, `.claude/settings.json` | Push to `main`, force-push, `--no-verify`, secrets in written files, reading `.env`, reading or printing the gh token |
| Pre-commit | `.githooks/pre-commit` (enabled by `post-create.sh`) | Commits with secrets — yours and the agent's |
| CI | `.github/workflows/ci.yml` | Lint, tests, gitleaks on the whole history |

Run the checks locally: `scripts/lint.sh` and `scripts/test.sh`.

## What is not in the container, on purpose

- **Cloud credentials** (gcloud, Terraform): cloud changes go through CI.
- **The Browser MCP endpoint (A-1)**: not in the network allowlist. Spike kits that need A-1 run outside the container.
- **Windows files**: nothing from the host is mounted except the workspace.

## Changing the environment

| Need | Change |
|---|---|
| Allow a new domain | Add it to `.devcontainer/allowed-domains.txt`, rebuild, explain why in the PR |
| Add a tool or language | `.devcontainer/Dockerfile` or a devcontainer feature, in a PR |
| Change Claude Code container settings | `.devcontainer/claude-settings.json` |

## Troubleshooting

| Problem | Fix |
|---|---|
| `init-firewall.sh: $'\r': command not found` | The script was checked out with CRLF. Re-clone after the `.gitattributes` change, or clone into a container volume |
| Firewall: "could not read GitHub IP ranges" | Network not ready at start — rebuild or restart the container |
| Commands fail with `bwrap: Unexpected capabilities but not setuid` | The runtime (e.g. rootless Podman) gave the firewall capabilities to the `node` user. Start Claude Code with `claude` (the wrapper in `/usr/local/bin` drops them); check `which claude` shows `/usr/local/bin/claude`; rebuild the container if it does not |
| Claude Code exits: sandbox unavailable | Check `bubblewrap` and `socat` are installed and `enableWeakerNestedSandbox` is `true` in `~/.claude/settings.json` inside the container |
| Commit blocked: "gitleaks found a possible secret" | Remove the value from the file and use a placeholder. If it is a false positive, add a narrow allowlist entry to `.gitleaks.toml` in a PR |
| Claude Code says gh is not authenticated, but `gh auth status` in the terminal is fine | A Read deny rule covers `~/.config/gh`, or the sandbox has not allowed `api.github.com` yet — approve the domain when Claude Code asks |
| `gh issue view` fails with "Projects (classic) is being deprecated" | Old `gh` from Debian; rebuild the container (it now installs `gh` from GitHub's repository). Until then: `gh issue view N --json title,body,comments` |
| Claude Code's first `gh` call fails with "not in this command's allowed_domains" | The sandbox allows network per command; Claude Code re-runs it with `api.github.com` listed. Approve it if asked |
| A service stopped working after hours | Its IPs changed; restart the container to re-resolve the allowlist |
