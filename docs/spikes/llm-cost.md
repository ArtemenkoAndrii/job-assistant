# Spike: LLM cost per run

| | |
|---|---|
| **Issue** | #3 |
| **Status** | Done |
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

### Tailoring on a matching vacancy (run 2026-11-23 15:05, `--tailor-vacancy`)

A backend platform role close to the owner's profile. Cost per call was the same as before (Luna $0.0012, Terra $0.0096, Sol $0.0176 for tailor).

- **All three models added no skills** and invented nothing; all kept the real achievements and adjusted emphasis. Terra's tailoring was the closest to Luna's; Sol restructured more (merged sections). With a matching vacancy, Terra did not over-add — its earlier problem shows up only under pressure from a mismatched vacancy.
- **All three reviewers answered "rework" because of missing requirements the original resume cannot support** (multi-region, third-party vendor integrations). That is a candidate–vacancy gap, not a resume defect; with this behaviour the tailor ↔ review loop would never converge. **Fixed in the review prompt:** the verdict judges only rule compliance and tailoring quality; gaps go to a separate `fit_gaps` list.

### Browsing tasks, first live run (2026-11-23 15:14, `agent_tasks.py`)

| Task | Luna | Terra |
|---|---|---|
| LinkedIn search | failed, 9 calls | failed, 7 calls |
| LinkedIn vacancy 1 | failed, 8 calls (cap) | done, 8 calls (cap) |
| LinkedIn vacancy 2 | done, 8 calls (cap) | failed, 8 calls (cap) |
| Glassdoor company | done, 10 calls (cap) | done, 10 calls (cap) |
| Avg cost per task | $0.0005–0.0012 | $0.0033–0.0062 |
| Time per task | 24–150 s | 84–147 s |

Findings:

- **The tool-call caps were too low**: every vacancy and company task used exactly the cap (8 / 10). Failures here say more about the cap than about the models. Caps raised to 20 / 20 / 40.
- **Both models failed the search task** — reason to be diagnosed from the task notes (now shown in the report).
- **Reported input tokens look too low** (2–10k for 7–10 tool calls on pages that are 5–8k tokens each in spike #2). Either the agent used small targeted reads, or the usage does not include the tool results. The report now shows the size of tool outputs next to input tokens to tell the two apart. **Until then, browsing cost is not trusted.**
- **Speed:** 1.5–2.5 minutes per vacancy through OpenAI → Cloudflare → A-1; 25 vacancies ≈ 40–60 minutes per run. Acceptable for a scheduled background job.

### Browsing tasks, second live run (2026-11-23 15:31, caps raised)

| Task | Luna | Terra |
|---|---|---|
| LinkedIn search | failed — page went blank | failed — page went blank |
| LinkedIn vacancy 1 | **done**, 6 calls, 14.4k tokens, $0.0016 | failed — page went blank |
| LinkedIn vacancy 2 | failed — details pane did not load | **done**, 9 calls, 8.0k tokens, $0.0097 |
| Glassdoor company | failed — tab switched to about:blank | **done**, 12 calls, 8.6k tokens, $0.0111 |

Findings:

- **Token accounting is correct.** Tool output size matches input tokens (e.g. 50k characters of page text ≈ 12.5k tokens vs 14.4k reported). The cost numbers can be trusted.
- **No task hit the cap any more.** The remaining failures are not about the models: in 5 of 8 tasks the agent reported that **the page became blank or switched to about:blank** between its own tool calls — on both LinkedIn and Glassdoor, so the cause is the browser session, not a site block.
- **Likely cause:** Playwright MCP creates a **new browser context per HTTP client** unless started with `--shared-browser-context`. When OpenAI's servers call A-1 through separate connections, a navigation and the following snapshot can land in different contexts. Spike #2 (Claude Code, one long connection) never saw this. To be confirmed on A-1.
- When the session held, **Luna completed a vacancy extraction in 6 calls for $0.0016** — 6× cheaper than Terra for the same task.

### Per run and per month (browsing + text steps)

Browsing cost from the successful tasks of the second run; text steps from the 15:05 run. One profile.

| Browsing | Writing | Per run | Light (3 runs/week) | Daily | Max (3 profiles daily) |
|---|---|---|---|---|---|
| **Luna** | **Luna writes, Sol reviews** | **$0.13** | **$1.69/mo** | **$3.94/mo** | **$11.81/mo** |
| Luna | Sol writes and reviews | $0.21 | $2.75/mo | $6.42/mo | $19.27/mo |
| Terra | Luna writes, Sol reviews | $0.35 | $4.60/mo | $10.72/mo | $32.17/mo |
| Terra | Sol writes and reviews | $0.44 | $5.66/mo | $13.21/mo | $39.63/mo |

## Recommendation

**Models per step (MVP):**

| Step | Model | Reasoning effort | Why |
|---|---|---|---|
| Browsing tasks (search, vacancy, company) | GPT-6 Luna | low | Completed the task when the session held, 6× cheaper than Terra; re-check success rate once sessions are fixed |
| Filter, dossier extraction | GPT-6 Luna | low | Same results as Terra and Sol at 1/10–1/20 of the cost |
| Resume tailoring | GPT-6 Luna | medium | Compliant with the added-skill rule in both runs; Terra over-added skills under pressure |
| Resume review | GPT-6.2 Sol | medium | The only reviewer that checked the added-skill rules; it is the safety net for "never invent experience" |

**Expected cost:** ~$0.13 per run of one profile → **~$1.7/month** at 3 runs a week, **~$4/month** daily, ~$12/month for 3 profiles daily.

**LLM cap:** **$10/month**, with an alert at $5. Covers daily runs of one profile with 2.5× margin and leaves room for retries and evals; the current $10 balance lasts 2–5 months.

**Not settled by this spike — moves to #19 / #20:**

- **Browser session stability through OpenAI's hosted MCP** (pages going blank). First check: start Playwright MCP on A-1 with `--shared-browser-context`. If that does not help, the agent loop must run in our code with one persistent MCP session (still OpenAI models, our own MCP client) — this also fits the `BrowserGateway` design.
- **Success rate of Luna as a browser agent** — to be measured once sessions are stable; Terra is the fallback model for browsing (~$0.35 per run).
- **Latency:** 15–140 s per task through OpenAI → Cloudflare → A-1; a run takes 30–60 minutes. Fine for scheduled runs.
- **Re-measure with evals (#25)** once the golden dataset exists — single-call quality findings here are indicative.
