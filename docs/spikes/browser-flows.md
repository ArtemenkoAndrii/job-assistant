# Spike: browser automation flows

| | |
|---|---|
| **Issue** | #2 |
| **Status** | Done |
| **Dates** | 2026-11-20 – 2026-11-22 |
| **Model used** | claude-sonnet-5-5 (Claude Code) |
| **How to run** | [spikes/browser-flows/README.md](../../spikes/browser-flows/README.md) |

## Goal

Find out whether an AI agent can reliably search vacancies and walk application flows on LinkedIn and Glassdoor through the Browser MCP endpoint (A-1), and what that costs.

## Summary

The agent can drive both sites through A-1: search with filters, read vacancy details and walk application forms up to the final step. **LinkedIn is the workhorse**: about 20–25 relevant vacancies per week, complete vacancy text, clear apply method. **Glassdoor adds little for search** (4 matching vacancies vs 20–25, mostly duplicates of LinkedIn) and **hides most review and salary data behind a give-to-get wall even when logged in**; its search was also blocked by Cloudflare on 2 of 3 attempts. Applications need three inputs the system does not have yet — a **phone number**, a **resume file available to the browser on A-1**, and **answers to screening questions** (up to 11 per vacancy, partly free text). Cost is dominated by large page snapshots re-read on every turn (60–75k tokens of context per turn in Claude Code); the runtime agent must work with targeted, short-lived contexts.

## 1. Connectivity

| Question | Answer |
|---|---|
| A-1 reachable through Cloudflare Access with service token | Yes |
| Typical latency per MCP call | Not measured precisely; whole scenarios took 2.5–5.5 min including user approvals |
| Session stayed logged in on both sites | **No.** LinkedIn was logged out at the start of scenario 01 (signed in manually with a dedicated account) and showed an authwall once in scenario 04 that disappeared on reload. Glassdoor stayed logged in. |

## 2. Search

| Question | LinkedIn | Glassdoor |
|---|---|---|
| Filters the agent could set | Keywords, date posted, workplace type; also Easy Apply, employment type, company, etc. Each filter = 3 clicks (open, select, "Show results") | Keywords, location, date posted, remote only, quick apply only, salary range |
| Filter state readable from URL | **Unreliable**: `f_TPR` works, but Remote produced an unrelated `f_SAL` param, and `f_WT=2` typed into the URL was dropped by a redirect | Yes: `fromAge=7`, `remoteWorkType=1` |
| Vacancies found (Lead Software Engineer, past week) | 20 remote (Spain-wide); 97 without date filter | 4 in Málaga; 1 when remote-only. The "related jobs" block is noise |
| Vacancies per results page | 25 | n/a (4 results) |
| Pagination | Numbered buttons, offset `start=25`, filters kept | Not tested (too few results) |
| Sign-in walls, hidden content | None for search once logged in | Job-alert dialog pops up after search; cards have no salary or work type |
| Bot protection or challenges | Authwall once (transient) | **Cloudflare Turnstile "Just a moment…" on 2 of 3 attempts** (HTTP 403); no challenge on the third |
| Stable element refs | No — refs go stale after every click or filter apply | No — card order changes between loads |

### Field availability on list cards

| Field | LinkedIn (25 cards) | Glassdoor (4 cards) |
|---|---|---|
| Title, company, location | 25/25 | 4/4 (location often just "España") |
| Work type | Only as "(Remote)" suffix in location | 0/4 |
| Salary | 3/25 | 0/4 |
| Posted date | 25/25, relative ("2 days ago") | 4/4, relative |
| Easy / quick apply | Label when yes (~14/25) | Label when yes (3/4) |
| Company rating | — | 4/4 |
| **Vacancy URL** | **Not on cards** — cards are buttons; the job id (`currentJobId`) appears only after clicking each card | Yes, on cards |

### Vacancy details (LinkedIn, 3 vacancies)

| Data | Availability |
|---|---|
| Full description | 3/3 — the accessibility snapshot contains the full text even behind "… more" |
| Required vs nice-to-have skills | Explicit in 1/3; otherwise needs LLM extraction |
| Salary | 0/3 |
| Seniority | Not a structured field; inferred from title and text |
| Work type, employment type | Chips present but **sometimes wrong** (a Principal role marked "Internship"); location in chips can conflict with the text |
| Apply method | 3/3 clear: "Easy Apply" or "Apply on company website" (real target URL readable from the `/safety/go/` redirect) |
| Company page | Link present (`/company/<slug>/life/`) |

## 3. Employer research (Glassdoor)

| Data | Available? | Notes |
|---|---|---|
| What the company does, size, HQ, founded | Yes | Overview is open |
| Overall rating, % recommend, CEO approval, category scores | Yes | Small samples look the same as large ones (one company had a rating from **1** review) |
| Review texts (pros / cons) | **Mostly no** | ~2 readable reviews per company; the rest blurred behind "share your experience to get full access" — even when logged in |
| Salary range for a similar role | **No** | 1 readable row per company; the rest blurred |
| Interview questions | Not checked | Page-load budget |

## 4. Application flows (dry-run)

Nothing was filled, uploaded or submitted.

| # | Source | Channel | Steps | Screening questions | File upload | Blockers | Stopped at |
|---|---|---|---|---|---|---|---|
| 1 | LinkedIn | Easy Apply (Greenhouse behind it; flow stays in the LinkedIn modal) | 4 | **11**: English level, salary expectation, years of experience, location, work permit, visa, privacy consent, etc. — selects, radios and free text | Resume DOC/DOCX/PDF < 2 MB; no saved resume on the account | Answers needed | Step 3 of 4, before "Review" |
| 2 | LinkedIn | Easy Apply | 4 | Not reached | Not reached | **Phone number required**, not in profile | Step 1 of 4 |
| 3 | LinkedIn → external | Ashby ATS (new tab), single page | 1 | Notice period, salary, location + **3 long free-text questions** | Resume required | Answers needed; no account or CAPTCHA | Before "Submit Application" |
| 4 | Glassdoor | Quick apply → **Indeed Smart Apply** (new tab, invisible reCAPTCHA) | ~5–7 | Not reached | Not reached | **Phone number required** | Step 1 |

**Resume upload:** Playwright MCP uploads files from the machine where the browser runs (A-1), not from the app. All flows that got that far require a resume file, and the LinkedIn account has no saved resume. The tailored resume therefore has to be delivered to A-1 (using a resume stored on the job-board account would defeat tailoring).

**No email-apply channel was seen** on any vacancy.

## 5. Size and cost (input for #3)

Numbers come from Claude Code sessions. They include Claude Code's own system prompt and tool definitions, so a lean runtime agent will use less.

| Scenario | MCP calls | Avg snapshot chars (max) | Input tokens total | of which cache writes | Output tokens | Turns | Avg context per turn |
|---|---|---|---|---|---|---|---|
| 01 LinkedIn search | 26 | 10.7k (20.8k) | 1.97M | 92k | 9.6k | 31 | ~64k |
| 02 LinkedIn details (3 vacancies) | 20 | 13.3k (30.7k) | 1.52M | 72k | 7.1k | 23 | ~66k |
| 03 Glassdoor | 50 | 4.1k (24.6k) | 4.68M | 118k | 19.2k | 62 | ~75k |
| 04 Apply dry-run (4 flows) | 32 | 12.0k (36.4k) | 2.76M | 120k | 13.6k | 43 | ~64k |

Observations:

- **Almost all input is cache reads**: the whole growing context is re-read every turn. Cost scales with *turns × context size*, not with pages visited.
- LinkedIn full-page snapshots are 50–70 KB; **targeted snapshots** (`target` = detail pane or dialog) and `browser_find` are several times cheaper.
- Reading 3 vacancy details took ~1.5M input tokens (~500k per vacancy) in one long session. That is far too expensive for a scheduled pipeline and needs a different design, not tuning.

## 6. Reliability and account safety

- **Failures:** 14 tool errors in 128 calls, mostly stale element refs after clicks and the `filename` parameter of snapshot/screenshot (paths are resolved on A-1 and fail with `EACCES`). Refs must be re-found after every click.
- **Challenges:** Glassdoor Cloudflare Turnstile (2 of 3 attempts), LinkedIn authwall (once, transient). No CAPTCHA was solved or clicked.
- **Unavoidable account side effects:** search keywords go to LinkedIn search history; opened vacancies are marked "Viewed".
- **Unexpected behaviour:** once a snapshot showed a LinkedIn page during a Glassdoor session (tab changed); link-outs open new tabs that stay open.
- **Credentials:** the LinkedIn password was typed into the browser through the agent, so it ended up in the session transcript and local recordings. It has to be changed, and the runtime must never handle job-board passwords — logging in is done manually on A-1.
- **Personal data:** snapshots contain the user's name, employer and city. Recordings must be anonymized before they become eval fixtures.

## 7. Implications

| For | Implication |
|---|---|
| #4 Application channels | Channels seen: LinkedIn Easy Apply, external ATS (Greenhouse, Ashby), Glassdoor → Indeed Smart Apply. No email-apply. Decide whether external ATS forms are in MVP or only Easy Apply. |
| Vision: profile data | Forms ask for data a resume doesn't have: **phone number, salary expectation, notice period, work permit / visa status, location and relocation preference**, years of experience per technology. Add them to the search profile. |
| Vision: screening answers | Up to 11 structured questions and several long free-text questions per application. Needs a policy: which the agent may answer from profile data, which need the user; the approval screen must show all answers. |
| #18 Data and file storage | The tailored resume must reach A-1 for upload (Playwright MCP reads files on the browser host): an upload endpoint or shared folder on A-1, or a fetch from storage. |
| #20 Browser automation policy | Allow `browser_find`; never use `filename` params; check the current tab first; stop on Turnstile, authwall or "Just a moment…"; close extra tabs; never type credentials. |
| #19 Agent runtime | Short, step-scoped contexts instead of one long session; targeted snapshots; extract structured data per page and drop the raw snapshot from context. The Claude Code numbers are an upper bound. |
| #24 Test dataset | Record per-page snapshots (search list, detail pane, apply dialog steps) as fixtures; anonymize personal data; drop any credential-typing calls. |
| Vision: Glassdoor scope | Low value as a vacancy source; company-level signals (rating, % recommend, size) are useful for the dossier; reviews, salaries and interview data mostly unavailable. |

## 8. Recommendation for MVP

1. **LinkedIn** stays the primary vacancy source; collect job ids by clicking cards (there are no URLs on cards).
2. **Glassdoor**: use it for employer dossier signals; keep it as a vacancy source only if later runs show unique vacancies. Treat Cloudflare challenges as a normal stop condition.
3. **Applying in MVP**: LinkedIn Easy Apply first, external ATS later. Extend the search profile with the fields the forms ask for, and show screening answers on the approval screen.
4. **Resume delivery to A-1** is a new architecture requirement (ADR #18).
5. **Cost**: design the runtime pipeline around targeted snapshots and short contexts before setting the LLM cap in #3.
