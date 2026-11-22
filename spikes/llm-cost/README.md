# Spike kit: LLM cost per run (#3)

Measures what each step of a **lean pipeline** costs on different models, using the real page snapshots recorded in spike #2. No Browser MCP (A-1) is needed: browsing is done by deterministic code in the real pipeline, so only the LLM steps are measured here. Findings go to [docs/spikes/llm-cost.md](../../docs/spikes/llm-cost.md).

## Pipeline steps measured

Each step is one short API call with its own system prompt (`prompts/`), not a long agent session.

| Step | Input | Calls per run (default) |
|---|---|---|
| `extract_list` | Search results page snapshot | 2 (pages) |
| `extract_vacancy` | Vacancy page snapshot | 25 |
| `filter` | Requirements + extracted vacancy | 25 |
| `dossier` | Company page snapshot (overview / reviews / salaries) | 8 companies × 3 pages |
| `tailor` | Resume + vacancy | 5 |
| `review` | Original + tailored resume + vacancy | 5 × 1.5 rounds |
| `nav_fallback` | LLM-driven browsing when a deterministic step fails | **estimated**, not measured |

Volumes, model mixes and monthly scenarios are in `assumptions.json`. Prices are in `pricing.json`.

## Before you start

- Recordings from spike #2 in `spikes/browser-flows/recordings/` (they stay on your machine).
- Your resume and requirements file (`.md`, `.txt` or `.pdf`).
- Python 3 and the SDK: `pip install anthropic pypdf`
- An Anthropic API key with a few dollars of credit ([console](https://console.anthropic.com/)). A full run on Haiku + Sonnet costs roughly **$0.10–0.30**; adding Opus roughly doubles it.

## Run

```powershell
cd C:\repo\Mas\job-assistant\spikes\llm-cost
$env:ANTHROPIC_API_KEY = Read-Host 'Anthropic API key'

# 1. Check which snapshots were picked — no API calls
python measure.py --resume C:\path\resume.md --requirements C:\path\requirements.md --dry-run

# 2. Measure
python measure.py --resume C:\path\resume.md --requirements C:\path\requirements.md --models haiku,sonnet,opus
```

Results go to `results\<timestamp>\` (git-ignored — they contain your resume and personal data):

- `report.md` — tokens and cost per step and model, cost per run for each mix, monthly projection for each scenario
- `calls.json` — every call with usage and the model's output, so you can **compare quality** between models

## Change assumptions without new API calls

Edit `assumptions.json` (volumes, mixes, scenarios) and rebuild the report:

```powershell
python measure.py --report-only results\<timestamp>
```

## What to send back

Send `report.md` (it has numbers only, no personal data) and your impression of output quality per model, especially for `tailor` and `review` in `calls.json`.
