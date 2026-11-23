# Spike: LLM cost per run

| | |
|---|---|
| **Issue** | #3 |
| **Status** | Pre-estimate done; measurement pending |
| **Date** | 2026-11-23 |
| **How to run** | [spikes/llm-cost/README.md](../../spikes/llm-cost/README.md) |

## Goal

Get a realistic monthly LLM budget for the pipeline, per step and per model, so that an LLM cap can be set (hosting has its own $5/month budget; LLM usage is separate — see vision §10).

## Decisions this spike works with

- **Provider:** OpenAI for the runtime agents (API balance already paid). Claude stays the development tool (Claude Code). The runtime keeps a provider abstraction (vision §10).
- **Architecture (MVP, #19):** an agent with **short tasks** over the Browser MCP endpoint — each task ("open vacancy X and extract it") is a fresh request with a small tool set and a tool-call cap. Spike #2 showed that one long agent session costs ~500k input tokens per vacancy, so long sessions are ruled out.

## Prices

USD per 1M tokens, short-context rates, official pricing pages checked 2026-11-23.

| Model | Input | Cached input | Output | Comparable Claude model |
|---|---|---|---|---|
| GPT-6 Luna | 0.10 | 0.01 | 0.50 | Haiku 5.5 (same price) |
| GPT-6.1 Terra | 1.00 | 0.05 | 5.00 | — (no Claude tier at this price) |
| GPT-6.2 Sol | 2.00 | 0.10 | 10.00 | Sonnet 5.5 (same price) |
| GPT-6.2 Astra | 8.00 | 0.40 | 40.00 | Opus 5.5 is half the price |

GPT-6 models are reasoning models: reasoning tokens are billed as output. The kit sets reasoning effort per step (`low` for extraction, filtering and browsing, `medium` for tailoring and review).

## Pre-estimate (before measurement)

Volumes per run of one search profile (`assumptions.json`): 2 search pages, 25 vacancies read and filtered, 8 companies researched, 5 resumes tailored, 1.5 review rounds each.

Token counts estimated from spike #2 snapshot sizes (~3.5 characters per token), **without reasoning tokens**: list page 4.3k in / 1.5k out, vacancy page 3.9k / 0.5k, filter 1k / 0.15k, company page 2.9k / 0.4k, tailoring 2.6k / 2k, review 4.5k / 0.4k.

| Mix | Per run | Light (1 profile, 3 runs/week) | Daily (1 profile, 7 runs/week) | Max (3 profiles, 7 runs/week) |
|---|---|---|---|---|
| All Luna | $0.05 | $0.71/mo | $1.66/mo | $4.99/mo |
| **Luna + Terra** (Terra writes resumes and reviews) | **$0.23** | **$3.02/mo** | **$7.04/mo** | **$21.12/mo** |
| Luna + Sol | $0.43 | $5.59/mo | $13.04/mo | $39.13/mo |
| All Terra | $0.54 | $7.05/mo | $16.46/mo | $49.37/mo |
| All Sol | $1.09 | $14.11/mo | $32.92/mo | $98.77/mo |

Takeaways so far:

- **Model choice for writing is the main cost lever**: Luna for everything is almost free; who writes the resume decides between ~$3 and ~$14 a month at 3 runs a week.
- **Short agent tasks** should cost about the same as the estimate if a cheap model can browse on its own: ~4 tool calls and ~25k input tokens per vacancy, mostly cached. If browsing needs a stronger model, the cost of the 25 vacancy tasks per run grows ~10–20× — this is the biggest unknown, measured by `agent_tasks.py`.
- Reasoning tokens are not in the estimate; with `low` effort they should add tens of percent, not multiples.
- The $10 OpenAI balance covers the measurement and the first months of the MVP at the light or daily scenario with Luna + Terra.

## Measurement

<To fill from `results/<timestamp>/report.md` (text steps) and `results/agent-<timestamp>/report.md` (browsing tasks).>

### Text steps (average per call)

| Step | Luna in / out / $ | Terra in / out / $ | Sol in / out / $ |
|---|---|---|---|
| extract_list | | | |
| extract_vacancy | | | |
| filter | | | |
| dossier | | | |
| tailor | | | |
| review | | | |

### Browsing tasks (live, through A-1)

| Task | Luna: success / tool calls / $ | Terra: success / tool calls / $ |
|---|---|---|
| LinkedIn search | | |
| LinkedIn vacancy | | |
| Glassdoor company | | |

### Per run and per month

| Browsing model | Writing model | Per run | Light | Daily | Max |
|---|---|---|---|---|---|
| | | | | | |

### Quality by model

| Step | Is Luna good enough? | Notes |
|---|---|---|
| Browsing tasks | | |
| filter | | |
| tailor | | |
| review | | |

## Recommendation

<Model per step, reasoning effort, monthly LLM cap, what to re-measure once evals (#25) exist.>
