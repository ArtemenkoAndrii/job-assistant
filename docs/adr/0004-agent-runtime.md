# ADR-0004: Agent runtime and LLM provider

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-24 |
| **Issue** | #19 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

The run worker executes the pipeline of UC-07: short browsing tasks (search, read a vacancy, research an employer) and single-call text steps (filter, dossier, tailor, review, answers). The web app runs a few interactive LLM steps outside the run queue (extraction preview, regenerating answers or a resume) — [architecture §2–§3](../architecture.md).

Decided earlier, recorded in #19:

- **Option C** for browsing: an LLM agent with short tasks over the Browser MCP (A-1) — fresh context per task, small tool set, turn limit. Reviewed after the MVP in #38.
- **OpenAI** is the runtime provider (API balance available); the design keeps a provider abstraction (vision §10).
- Spike #3 ([LLM cost](../spikes/llm-cost.md)) measured models per step and recommended GPT-6 Luna for most steps and GPT-6.2 Sol for resume review.

Still open, and the reason for this ADR:

- **Where the agent loop runs.** Spike #3 used the Responses API **hosted MCP tool**: OpenAI's servers called A-1 directly. In 5 of 8 tasks the page went blank between calls (likely a new browser context per connection). With a hosted tool, Job Finder also cannot pause between calls, count page loads or stop before the next call after an authwall, and the A-1 token is sent to the provider with every request.
- **Which harness** runs the loop, how the provider is abstracted, and how cost is measured and capped.
- The owner chose **Python** for the product code (input to the stack ADR, #46).

## Decision drivers

- Browsing rules enforced in code, not in prompts: read-only tool allowlist, limits, pace, stop conditions (NFR-B1–B7, NFR-S6) — all browsing through `BrowserGateway` (NFR-M2).
- Provider abstraction: changing the model or provider of a step is configuration plus an eval run (NFR-M1).
- Cost recorded per step and capped per month (NFR-C2–C4); a task cannot loop without bound.
- Personal data sent to the provider only as needed, not stored or used for training (NFR-P5, NFR-P6).
- Testable without the real LLM or A-1: fake models in unit tests, fake MCP server in CI (NFR-M5, #24); evals gate prompt and model changes (NFR-Q4, #25).
- Simple, well known and typed, so agents writing the code get it right; few dependencies (CLAUDE.md: prefer the simplest thing).

## Options considered

### Where the loop runs

**L1. Hosted MCP tool (the provider calls A-1).** Least code.
- Bad: blank pages seen in spike #3; no deterministic pace, counters or stop checks between tool calls; A-1 token leaves our infrastructure; A-1 must accept calls from the provider's network.

**L2. Loop in the worker (our code executes each tool call).** The model returns tool calls; the worker runs them through `BrowserGateway` over one MCP session and sends the results back.
- Good: every browser call passes our allowlist, counters, pace and stop detection; the A-1 token stays in the worker; one MCP session for the whole task.
- Bad: one more component to write and test (the gateway); latency of an extra hop is negligible against 1–5 s pauses.

### Harness for L2

**H1. OpenAI Agents SDK (Python).** Agents, tools, `max_turns`, guardrails; connects to MCP servers over Streamable HTTP from our process with headers and a tool filter.
- Good: first-party for OpenAI models; MCP support built in.
- Bad: OpenAI-first; other providers through an adapter. Tracing goes to OpenAI by default and must be turned off for personal data. Its built-in MCP connection would bypass our gateway unless we wrap it.

**H2. Pydantic AI.** Typed agents with structured output, function tools, `UsageLimits` (requests, tool calls, tokens per run), first-class providers (OpenAI Responses, Anthropic, Google, …), `TestModel` and `FunctionModel` for tests without an LLM, MCP client support.
- Good: provider-neutral by design (NFR-M1); typed outputs fit the extraction and review steps; per-run limits built in; offline test models; no tracing unless configured.
- Bad: one more dependency than raw SDK calls; its own release cadence to follow.

**H3. Own thin loop** on the OpenAI Responses API plus the official `mcp` client.
- Good: no framework; full control.
- Bad: we write and maintain tool-call parsing, retries, structured output, usage accounting, limits and a provider abstraction — all of which H2 already has and tests.

Graph frameworks (e.g. LangGraph) were not considered further: the pipeline is a fixed sequence of steps, plain code is enough.

## Decision

**L2 + H2: the agent loop runs in the worker, on Pydantic AI, with OpenAI as the provider.**

1. **Pipeline in plain Python.** The orchestrator calls steps in order (UC-07); no agent framework decides the flow. Each step is a Pydantic AI agent with a typed output model, or a single call.
2. **Browsing agents get gateway tools, not MCP tools.** A browsing task's tools are a few Python functions (`navigate`, `snapshot`, `find`, `click`, `back`, `tabs`) implemented by `BrowserGateway`. The gateway holds one MCP client session to A-1 (official `mcp` Python package, Streamable HTTP, Cloudflare Access headers from the secret manager) and, on every call: checks the allowlist and arguments, waits the random 1–5 s pace, counts page loads, calls A-1, checks the result for stop conditions and raises `BrowserBlocked` if one is found. The model never sees MCP or A-1. Which tools and clicks are allowed is set in the browser policy ADR (#20).
3. **LLM gateway.** A thin module in front of Pydantic AI:
   - a **model registry** in configuration: step → provider, model, reasoning effort, `UsageLimits`;
   - **cost** = usage tokens × a price table in configuration (as in the spike's `pricing.json`), written to the cost ledger per step and run (NFR-C3);
   - **budget guard**: before each task, the month's spend from the ledger plus the task's worst case must stay under the cap, otherwise `BudgetExceeded` → run *stopped: budget* (NFR-C4). The worst case is the task's token ceiling (point 4) × the model's prices. Alert at $5 (NFR-C2);
   - **provider settings**: OpenAI Responses API with `store=false`; no third-party tracing; our own step trace in the DB without resume text, kept ≤ 30 days (NFR-P6);
   - **provider abstraction check** (NFR-M1): a test runs one step on two providers' model classes (with recorded responses), so a second provider stays wired.
4. **Per-task ceilings** with Pydantic AI `UsageLimits` (requests, tool calls and total tokens), so no task loops and every task has a known worst-case cost. Starting values, from the spike kit, tuned with real runs:

   | Task | Tool calls | Requests | Total tokens | Worst case on Luna |
   |---|---|---|---|---|
   | Search (per source) | 40 | 45 | 400k | ~$0.04 |
   | Read vacancy, research employer | 20 | 25 | 200k | ~$0.02 |
   | Text step (one call) | 0 | 3 | 30k | < $0.01 (Sol review ~$0.30) |

   Tailor/review rounds are counted by the orchestrator (max 2 rework rounds). Search never succeeded in spike #3 (blank pages), so its ceiling is the least certain.
5. **Web search** for the dossier uses the provider's built-in web search tool through the same gateway (cost counted per call).

**Model per step (from spike #3; changed only through configuration and evals):**

| Step | Where | Model | Effort | Expected cost |
|---|---|---|---|---|
| Search, read vacancy, research employer (browsing tasks) | worker | GPT-6 Luna | low | ~$0.002 per task |
| Dedupe (job id; company + title, UC-15) | worker | none — code | — | — |
| Extract list / vacancy, hard filter, re-filter, dossier synthesis | worker | GPT-6 Luna | low | < $0.002 per call |
| Dossier web search | worker | provider web search | — | ~$0.01 per call, ~$0.08 per run |
| Tailor resume | worker, web (UC-12) | GPT-6 Luna | medium | ~$0.0013 per vacancy |
| Review resume | worker, web (UC-12) | GPT-6.2 Sol | medium | ~$0.013 per vacancy |
| Answers, cover note | worker, web (UC-11 A1) | GPT-6 Luna | low | < $0.002 per package |
| Extraction preview on upload | web (UC-03) | GPT-6 Luna | low | < $0.002 per file |

**Expected total:** ~$0.15–0.25 per run of one profile, ~$1/month on the weekly schedule (NFR-C5). Fallback for browsing if Luna's task success rate is too low: GPT-6.1 Terra (~$0.43 per run including web search), a configuration change.

**Provider data terms:** OpenAI does not use API data for training by default; abuse-monitoring logs are kept up to 30 days. Responses are not stored (`store=false`). Zero Data Retention needs OpenAI's approval and is not required for the MVP (NFR-P5).

Out of scope: browser tool allowlist, limits and stop triggers in detail (#20); language versions, packaging and project layout (#46); eval suite (#25).

## Consequences

- Positive: browsing rules are code paths with tests, not instructions a model may ignore; the A-1 token never leaves the worker; the blank-page problem of the hosted tool is avoided.
- Positive: switching a step to another model or provider is a registry change; unit tests run on `TestModel`/`FunctionModel`, CI on a fake MCP server, so no test calls OpenAI or A-1.
- Positive: cost is known per step and per run, and a run cannot exceed the monthly cap.
- Negative: we own `BrowserGateway` and the LLM gateway — small, but critical code that needs good tests.
- Negative: a dependency on Pydantic AI and on the `mcp` package; pin versions and update through PRs with evals.
- Risk: the session behaviour of Playwright MCP on A-1 with one long client session (and with newer, stateless MCP revisions) is not yet verified; checked in #20 together with `--shared-browser-context`.
- Follow-ups:
  - #20 browser automation policy: tool allowlist incl. which clicks, limits, stop detection, A-1 server flags.
  - #46 application stack: Python confirmed by the owner; versions, package manager, layout.
  - #22 walking skeleton: one browsing task through `BrowserGateway` and one Luna call with cost recorded.
  - #24/#25: fake MCP server and evals; re-measure Luna's browsing success rate.
  - On acceptance: status, ADR index in CLAUDE.md and the "(Proposed)" mark in [architecture](../architecture.md) Q6 are updated in this PR.
