# Spike kit: browser automation flows (#2)

Everything needed to run spike #2 locally with Claude Code against the Browser MCP endpoint (A-1). Findings go to [docs/spikes/browser-flows.md](../../docs/spikes/browser-flows.md).

The kit is reusable later for recording MCP fixtures (#24).

## What is in here

| File | Purpose |
|---|---|
| `.mcp.json` | Connects Claude Code to A-1 and sends the Cloudflare Access service-token headers (`CF-Access-Client-Id`, `CF-Access-Client-Secret`) from environment variables |
| `set-credentials.ps1` | Asks for the MCP URL, Client Id and Client Secret and sets them for the current terminal only |
| `check-connection.ps1` | Verifies that Cloudflare Access accepts the token and the MCP server answers, before starting Claude |
| `.claude/settings.json` | Read-only browser tools allowed; clicks and typing ask you first; JavaScript execution, Bash and web access denied |
| `CLAUDE.md` | Safety rules for every session: never submit, never change the account, stop on any challenge |
| `prompts/` | One prompt per scenario |
| `extract.py` | Pulls MCP calls and token usage out of a session transcript |

## Before you start

- Claude Code installed on your machine.
- Python 3 (`winget install Python.Python.3.12` on Windows).
- A-1 is up and its LinkedIn and Glassdoor sessions are logged in.
- A Cloudflare Access **service token** for the A-1 application (see below).

## Cloudflare Access service token

A-1 sits behind Cloudflare Access, so every request must carry two headers: `CF-Access-Client-Id` and `CF-Access-Client-Secret`. `.mcp.json` adds them automatically from environment variables.

If you don't have a token yet:

1. Cloudflare Zero Trust → **Access → Service credentials → Service Tokens → Create Service Token**. Copy the Client Id and Client Secret (the secret is shown only once). Menu names in the dashboard may differ slightly.
2. In the Access application for your MCP hostname, add a policy with action **Service Auth** that includes this service token. A policy with action *Allow* is meant for people signing in and will redirect the token to a login page.

Treat the secret like a password: don't paste it into files, chats or commits.

## 1. Copy the kit out of the repo

Recordings and notes contain personal data (your name, profile, vacancies you looked at). The repository is public, so run the spike **outside** it:

```powershell
Copy-Item -Recurse .\spikes\browser-flows C:\spikes\browser-flows
cd C:\spikes\browser-flows
```

## 2. Set credentials for this terminal only

```powershell
. .\set-credentials.ps1
```

Note the leading dot: the script must be dot-sourced so the variables stay in your terminal. It asks for the MCP URL (ending with `/mcp`), Client Id and Client Secret (hidden input). Nothing is written to disk or to the PowerShell history. Repeat in every new terminal.

If PowerShell blocks scripts, allow them for this terminal: `Set-ExecutionPolicy -Scope Process Bypass`.

## 3. Check the connection

```powershell
.\check-connection.ps1
```

| Result | Meaning |
|---|---|
| `OK` | Token accepted, MCP server answered — continue |
| Cloudflare Access did not accept the token | Wrong Id / Secret, or the Access policy is not *Service Auth* / doesn't include the token |
| 401 / 403 not from Cloudflare | Playwright MCP's host check rejected the hostname — start it on A-1 with `--allowed-hosts <your-mcp-host>` |

Then start Claude Code in the same terminal:

```powershell
claude
```

Approve the `browser` server when asked, then run `/mcp`: the server should be connected and list `browser_*` tools.

Pick the model you expect to use at runtime with `/model` and keep it for all scenarios; token numbers depend on it.

## 4. Run scenarios — one Claude Code session per scenario

For each prompt in `prompts/`, in order:

1. Edit the placeholders (search criteria, URLs).
2. Start a fresh session (`claude`) in the same terminal, paste the prompt.
3. Approve or reject each click / typing step. **Reject anything that would submit or change your account.**
4. When done, `/exit` and record the session:

```powershell
python extract.py 01-linkedin-search
```

This writes `recordings/01-linkedin-search/calls.jsonl` and `summary.md`.

| # | Scenario | Prompt |
|---|---|---|
| 1 | LinkedIn search | `prompts/01-linkedin-search.md` |
| 2 | LinkedIn vacancy details | `prompts/02-linkedin-details.md` |
| 3 | Glassdoor search + employer research | `prompts/03-glassdoor.md` |
| 4 | Application dry-run (3-5 flows) | `prompts/04-apply-dry-run.md` |
| 5 | Channel census for #4 (read only, ~25 + 10 vacancies) | `prompts/05-channel-census.md` |

## 5. Write up findings

Fill in [docs/spikes/browser-flows.md](../../docs/spikes/browser-flows.md) in the repo using `notes/` and `recordings/*/summary.md`. Copy **conclusions and numbers only** — no raw recordings, names or personal details.

## Stop conditions

Stop the whole spike and note it in the findings if you see a CAPTCHA, a verification or login challenge, an "unusual activity" warning, or any restriction notice on either account.
