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
| Claude Code exits: sandbox unavailable | Check `bubblewrap` and `socat` are installed and `enableWeakerNestedSandbox` is `true` in `~/.claude/settings.json` inside the container |
| A service stopped working after hours | Its IPs changed; restart the container to re-resolve the allowlist |
