---
name: cost-guard
description: Cost policy for Job Finder. Use when writing or reviewing a spec, plan or code change that adds or changes LLM calls, prompts, models, agent tasks, web search, browsing volume, scheduled jobs or cloud resources. Estimates the effect on the $5/month hosting budget and the $10/month LLM cap.
---

# Cost check

Budgets: hosting ≤ **$5/month** (NFR-C1), LLM ≤ **$10/month**, alert at $5 (NFR-C2). Expected today: ~$0.15–0.25 per run of one profile, one run a week → ~$1/month (NFR-C5).

## LLM

For every new or changed LLM call or agent task, write a line:

```
<step>: <model>, ~<input> in / ~<output> out tokens, × <calls per run> = ~$<per run>
```

Reference figures (spike #3, `docs/spikes/llm-cost.md`; USD per 1M tokens, input / output):

| Model | Price | Use for |
|---|---|---|
| GPT-6 Luna | 0.10 / 0.50 | Browsing tasks, extraction, filtering, dossier, tailoring |
| GPT-6.2 Sol | 2.00 / 10.00 | Resume review |
| Web search | ~$0.01 per call | Dossier, ≤ 1 call per employer |

Typical sizes: vacancy page 4–8k tokens; one browsing task ~6–15k tokens; tailoring ~3k in / 2k out.

Checks:

- [ ] Cheapest model that passes the evals for the step; a stronger model is justified in the spec (NFR-Q4).
- [ ] Context is step-scoped: no accumulated history, targeted page reads instead of full snapshots.
- [ ] Reasoning effort set explicitly (`low` unless the step needs more; reasoning tokens are billed as output).
- [ ] Retry and rework loops are bounded (e.g. review max 2 rounds).
- [ ] Cost per step is recorded in the run (NFR-C3) and the budget stop still works (NFR-C4).

## Browsing volume

- [ ] Stays within NFR-B2…B6 (pages, vacancies, employers per run; page loads per day; pauses).

## Cloud

- [ ] New resources stay within free tier, or the monthly cost is estimated and stays under NFR-C1 in total.
- [ ] Scheduled jobs and storage growth estimated (retention NFR-P3 keeps storage bounded).

## Output

Write into the spec's *Security, privacy and cost* section:

```
Cost: +$<x> per run (≈ $<y>/month on the weekly schedule); cloud: <free tier / +$z per month>
```

If the change pushes the expected total above half of a budget, add it to *Flagged concerns*.
