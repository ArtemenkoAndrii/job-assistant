# Spike kit: browser automation flows (#2)

Everything needed to run spike #2 locally with Claude Code against the Browser MCP endpoint (A-1). Findings go to [docs/spikes/browser-flows.md](../../docs/spikes/browser-flows.md).

The kit is reusable later for recording MCP fixtures (#24).

## What is in here

| File | Purpose |
|---|---|
| `.mcp.json` | Connects Claude Code to A-1; URL and Cloudflare Access token come from environment variables |
| `.claude/settings.json` | Read-only browser tools allowed; clicks and typing ask you first; JavaScript execution, Bash and web access denied |
| `CLAUDE.md` | Safety rules for every session: never submit, never change the account, stop on any challenge |
| `prompts/` | One prompt per scenario |
| `extract.py` | Pulls MCP calls and token usage out of a session transcript |

## Before you start

- Claude Code installed on your machine.
- Python 3 (`winget install Python.Python.3.12` on Windows).
- A-1 is up and its LinkedIn and Glassdoor sessions are logged in.

## 1. Copy the kit out of the repo

Recordings and notes contain personal data (your name, profile, vacancies you looked at). The repository is public, so run the spike **outside** it:

```powershell
Copy-Item -Recurse .\spikes\browser-flows C:\spikes\browser-flows
cd C:\spikes\browser-flows
```

## 2. Set credentials for this terminal only

```powershell
$env:A1_MCP_URL = "https://<your-mcp-host>/mcp"
$env:CF_ACCESS_CLIENT_ID = "<client id>"
$env:CF_ACCESS_CLIENT_SECRET = "<client secret>"
```

Do not put them in files.

## 3. Check the connection

```powershell
claude
```

Approve the `browser` server when asked, then run `/mcp`: the server should be connected and list `browser_*` tools.

Pick the model you expect to use at runtime with `/model` and keep it for all scenarios; token numbers depend on it.

## 4. Run scenarios — one Claude Code session per scenario

For each prompt in `prompts/`, in order:

1. Edit the placeholders (search criteria, URLs).
2. Start a fresh session (`claude`), paste the prompt.
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

## 5. Write up findings

Fill in [docs/spikes/browser-flows.md](../../docs/spikes/browser-flows.md) in the repo using `notes/` and `recordings/*/summary.md`. Copy **conclusions and numbers only** — no raw recordings, names or personal details.

## Stop conditions

Stop the whole spike and note it in the findings if you see a CAPTCHA, a verification or login challenge, an "unusual activity" warning, or any restriction notice on either account.
