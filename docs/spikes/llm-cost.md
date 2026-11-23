# Spike: LLM cost per run

| | |
|---|---|
| **Issue** | #3 |
| **Status** | Text steps measured; browsing tasks pending |
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

### Text steps (run 2026-11-23, `measure.py`)

Inputs: spike #2 snapshots (1 LinkedIn list page, 3 vacancy pages, 3 Glassdoor pages), the owner's real resume and a short requirements file. Reasoning effort: `low` for extraction, filter and dossier; `medium` for tailor and review. One call per vacancy / page, so quality findings are indicative, not statistically solid.

Average per call (input / output tokens incl. reasoning / cost):

| Step | Luna | Terra | Sol |
|---|---|---|---|
| extract_list | 8.1k / 1.4k / $0.0015 | 8.1k / 1.3k / $0.0144 | 8.1k / 1.3k / $0.0288 |
| extract_vacancy | 6.6k / 0.3k / $0.0008 | 6.6k / 0.3k / $0.0082 | 6.6k / 0.4k / $0.0172 |
| filter | 0.5k / 0.2k / $0.0002 | 0.5k / 0.1k / $0.0010 | 0.6k / 0.1k / $0.0023 |
| dossier | 4.0k / 0.1k / $0.0004 | 4.0k / 0.1k / $0.0045 | 4.0k / 0.1k / $0.0089 |
| tailor | 1.9k / 2.2k / $0.0013 | 2.0k / 2.1k / $0.0124 | 2.1k / 1.4k / $0.0185 |
| review | 3.4k / 0.8k / $0.0008 | 3.6k / 0.4k / $0.0056 | 3.4k / 0.7k / $0.0133 |

Real token counts are ~1.5× the pre-estimate on inputs (snapshots tokenize denser than 3.5 chars/token); reasoning added 10–40% to output on Luna, little on Sol. The per-run totals still match the pre-estimate.

Per run of one profile (text steps measured; browsing fallback still estimated):

| Mix | Per run | Light (3 runs/week) | Daily | Max (3 profiles daily) |
|---|---|---|---|---|
| All Luna | $0.060 | $0.77/mo | $1.81/mo | $5.42/mo |
| Luna + Terra writes | $0.228 | $2.97/mo | $6.93/mo | $20.78/mo |
| **Luna + Sol reviews** | **$0.231** | **$3.00/mo** | **$7.00/mo** | **$20.99/mo** |
| Luna + Sol writes | $0.403 | $5.23/mo | $12.21/mo | $36.64/mo |
| All Sol | $1.122 | $14.59/mo | $34.03/mo | $102.10/mo |

### Quality by model (text steps)

| Step | Is Luna good enough? | Notes |
|---|---|---|
| extract_list | Yes | All three extracted 25/25 cards with the same fields. Job ids are not on cards (spike #2), so `null` is correct. |
| extract_vacancy | Yes | All three extracted skills, work type and apply method correctly and flagged the same conflicts (the "Internship" label on a Principal role, Málaga vs Madrid office). Luna kept tracking parameters in one URL — trivial to clean in code. |
| filter | Yes | All three rejected the same 3 vacancies for the same, correct reasons (stack, office days, on-site). Scores within 15 points. |
| dossier | Yes | Equal on the one readable page; 2 of 3 picked pages were empty or walled, so this needs the live run. Sol answered in the page's language (Spanish). |
| tailor | **Maybe** — see below | Tested against a vacancy the filter rejected (Python/React role), which over-stresses the added-skill rule. Luna added 3 learnable AI skills tied to a stated requirement — compliant. **Terra added 9 skills incl. Python, TypeScript, Node.js and React** — not defensible after "a couple of days" for a Staff role: violates the rule. Sol added 3, one of them only nice-to-have (Temporal) — minor violation. No model invented roles, dates or achievements. |
| review | **No — use Sol** | All three said "rework" (correct for a mismatched vacancy). Only Sol checked the added-skill rules explicitly and caught its own tailor's Temporal violation; Luna and Terra reviewed against vacancy fit only. |

Takeaways:

- **Luna is enough for extraction, filtering and dossier** at ~1/10 of Terra and ~1/20 of Sol.
- **Terra is not a safe resume writer** under our rules: it over-adds skills. Price alone would favour it; quality does not.
- **The reviewer is the safety net for the "never invent experience" rule**, so it is worth paying for: Luna writes, Sol reviews costs the same as Luna + Terra (~$0.23 per run).
- Tailoring must be re-checked on a **matching** vacancy (`--tailor-vacancy`), and later continuously by evals (#25).

### Browsing tasks (live, through A-1)

| Task | Luna: success / tool calls / $ | Terra: success / tool calls / $ |
|---|---|---|
| LinkedIn search | | |
| LinkedIn vacancy | | |
| Glassdoor company | | |

### Per run and per month (browsing + text steps)

| Browsing model | Writing | Per run | Light | Daily | Max |
|---|---|---|---|---|---|
| | | | | | |

## Recommendation

<Model per step, reasoning effort, monthly LLM cap, what to re-measure once evals (#25) exist.>
