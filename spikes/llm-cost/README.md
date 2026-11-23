# Spike kit: LLM cost per run (#3)

Measures what the pipeline costs on OpenAI models (Claude models supported for comparison). Findings go to [docs/spikes/llm-cost.md](../../docs/spikes/llm-cost.md).

MVP architecture (decision in #19): **an agent with short tasks** over the Browser MCP endpoint (A-1) — each task ("open vacancy X and extract it") is a fresh, small request. Two scripts measure the two kinds of work:

| Script | Measures | Needs A-1 | Time |
|---|---|---|---|
| `measure.py` | Steps that only read or write text: filter, tailor, review (also extract / dossier from recorded pages, for comparison) — on page snapshots recorded in spike #2 | No | ~5 min |
| `agent_tasks.py` | Browsing tasks: LinkedIn search, LinkedIn vacancy, Glassdoor company — live, through A-1 | Yes | ~15 min |

`agent_tasks.py` combines both into the cost per run and per month.

## Files

| File | Purpose |
|---|---|
| `pricing.json` | Prices and API model ids (OpenAI: Luna, Terra, Sol; Claude: Haiku, Sonnet) |
| `assumptions.json` | Volumes per run, reasoning effort per step, model mixes, usage scenarios |
| `prompts/` | System prompts per step and per agent task; `agent_rules.md` holds the agent's hard rules |
| `tasks.json` | The live agent tasks — fill in real URLs before running |

## Before you start

- OpenAI API key with balance on platform.openai.com. Both measurements together cost roughly **$0.50–1**.
- Python 3: `pip install openai pypdf`
- Recordings from spike #2 in `spikes/browser-flows/recordings/`.
- Your resume and requirements file (`.md`, `.txt` or `.pdf`).
- For `agent_tasks.py`: A-1 is up, LinkedIn and Glassdoor are logged in, and you have the Cloudflare Access service token.

## 0. Check model ids

```powershell
cd C:\repo\Mas\job-assistant\spikes\llm-cost
$env:OPENAI_API_KEY = Read-Host 'OpenAI API key'
python measure.py --list-models
```

If a model in `pricing.json` is reported as not available, replace its `model` id with the one from the list.

## 1. Text steps (offline)

```powershell
python measure.py --resume C:\path\resume.md --requirements C:\path\requirements.md --dry-run
python measure.py --resume C:\path\resume.md --requirements C:\path\requirements.md --models luna,terra,sol
```

Result: `results\<timestamp>\report.md` and `calls.json` (with each model's output — compare the tailored resumes).

## 2. Browsing tasks (live, through A-1)

1. Fill in `tasks.json`: two real LinkedIn job ids and one Glassdoor company reviews URL (you can take them from spike #2 notes). Adjust the search URL keywords if you like.
2. Set credentials in the same terminal and check the connection:

```powershell
. ..\browser-flows\set-credentials.ps1
..\browser-flows\check-connection.ps1
```

3. Run:

```powershell
python agent_tasks.py --dry-run
python agent_tasks.py --models luna,terra --measure-results results\<timestamp from step 1>
```

How it works: each task is one OpenAI Responses API request with A-1 attached as a remote MCP server. The Cloudflare Access headers are sent with it; only read and navigation tools are allowed (no typing, uploads or JavaScript); tool calls per task are capped. OpenAI's servers connect to A-1 — page content goes to OpenAI, as it would with any hosted model.

Result: `results\agent-<timestamp>\report.md` — per task: success, tool calls, tokens, cost; per run and per month for each browsing model + writing model combination.

## Change assumptions without new API calls

Edit `assumptions.json`, then:

```powershell
python measure.py --report-only results\<timestamp>
python agent_tasks.py --report-only results\agent-<timestamp> --measure-results results\<timestamp>
```

## What to send back

Both `report.md` files (numbers only) and your impression of quality: are Luna's tailored resumes acceptable, did Luna manage the browsing tasks?
