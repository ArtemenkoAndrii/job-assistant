# Spike: LLM cost per run

| | |
|---|---|
| **Issue** | #3 |
| **Status** | Pre-estimate done; measurement pending |
| **Date** | 2026-11-22 |
| **How to run** | [spikes/llm-cost/README.md](../../spikes/llm-cost/README.md) |

## Goal

Get a realistic monthly LLM budget for the pipeline, per step and per model, so that an LLM cap can be set (hosting has its own $5/month budget; LLM usage is separate — see vision §10).

## Approach

Spike #2 showed that a long agent session is the wrong cost model: Claude Code re-read 60–75k tokens of context on every turn, about 500k input tokens per vacancy read. The runtime pipeline will instead be **deterministic code that drives the browser** plus **one short, focused LLM call per step**, with only the data that step needs. This spike measures those calls on the real page snapshots recorded in spike #2.

Prices (USD per 1M tokens, platform.claude.com pricing, checked 2026-11-22):

| Model | Input | Output | Cache read | Notes |
|---|---|---|---|---|
| Haiku 5.5 | 0.10 | 0.50 | 0.01 | Prompts over 100k tokens: 0.50 / 2.50. New tokenizer uses ~30% more tokens than Haiku 4.5 |
| Sonnet 5.5 | 2.00 | 10.00 | 0.10 | |
| Opus 5.5 | 4.00 | 20.00 | 0.20 | |

Volumes per run of one search profile (`spikes/llm-cost/assumptions.json`): 2 search pages, 25 vacancies read and filtered, 8 companies × 3 pages researched, 5 resumes tailored, 1.5 review rounds each, LLM-driven browsing fallback for 10% of vacancies.

## Pre-estimate (before measurement)

Token counts estimated from spike #2 snapshot sizes (~3.5 characters per token): list page 4.3k in / 1.5k out, vacancy page 3.9k / 0.5k, filter 1k / 0.15k, company page 2.9k / 0.4k, tailoring 2.6k / 2k, review 4.5k / 0.4k.

| Mix | Per run | Per tailored vacancy | Light (1 profile, 3 runs/week) | Daily (1 profile, 7 runs/week) | Max (3 profiles, 7 runs/week) |
|---|---|---|---|---|---|
| All Haiku | $0.06 | $0.01 | $0.71/mo | $1.66/mo | $4.99/mo |
| **Mixed** (Haiku; Sonnet for tailor, review, fallback) | **$0.43** | **$0.09** | **$5.59/mo** | **$13.04/mo** | **$39.13/mo** |
| All Sonnet | $1.09 | $0.22 | $14.11/mo | $32.92/mo | $98.77/mo |
| All Opus | $2.17 | $0.43 | $28.22/mo | $65.85/mo | $197.54/mo |

Takeaways so far:

- The lean design is **~10× cheaper per vacancy read** than the Claude Code session in spike #2 (about $0.01 vs $0.13 on Sonnet).
- In the mixed setup most of the cost is the **Sonnet steps**: browsing fallback (~40%), tailoring and review (~50% together). Extraction and filtering on Haiku are almost free.
- The browsing fallback is an assumption; if deterministic navigation is reliable, the mixed run drops to about $0.26.
- Volume is the main lever: the "max" scenario costs 7× the "light" one with the same mix.

## Measurement

<To fill from `results/<timestamp>/report.md`.>

### Per step (average per call)

| Step | Haiku in / out / $ | Sonnet in / out / $ | Opus in / out / $ |
|---|---|---|---|
| extract_list | | | |
| extract_vacancy | | | |
| filter | | | |
| dossier | | | |
| tailor | | | |
| review | | | |

### Per run and per month

| Mix | Per run | Per tailored vacancy | Light | Daily | Max |
|---|---|---|---|---|---|
| All Haiku | | | | | |
| Mixed | | | | | |
| All Sonnet | | | | | |

### Quality by model

| Step | Is Haiku good enough? | Notes |
|---|---|---|
| extract_list | | |
| extract_vacancy | | |
| filter | | |
| dossier | | |
| tailor | | |
| review | | |

## Recommendation

<Model per step, monthly LLM cap, what to measure again once evals (#25) exist.>
