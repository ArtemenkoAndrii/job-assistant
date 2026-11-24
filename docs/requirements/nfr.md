# Non-functional requirements (MVP)

| | |
|---|---|
| **Issue** | #7 |
| **Status** | For acceptance |
| **Based on** | [Vision v1](../vision.md), [use cases](use-cases.md), spikes [#2](../spikes/browser-flows.md), [#3](../spikes/llm-cost.md), [#4](../spikes/application-channels.md) |
| **Last updated** | 2026-11-23 |

Each requirement has an ID, a measurable target and a way to verify it. Values that answered open questions of the vision are listed in §12. ADRs and specs refer to these IDs.

## 1. Cost

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-C1 | Hosting and infrastructure cost | ≤ **$5/month** | GCP billing budget with alerts at 50%, 90%, 100% |
| NFR-C2 | LLM cost cap | ≤ **$10/month**, alert at **$5** | Provider budget / usage alert; monthly report |
| NFR-C3 | LLM cost is recorded per run and per step | 100% of runs | Run record has cost per step; checked in tests |
| NFR-C4 | Reaching the LLM cap stops runs | The next LLM step does not start; run status *stopped: budget* | Test with a lowered cap |
| NFR-C5 | Expected LLM cost | ~$0.15–0.25 per run of one profile (spike #3: $0.13 + web search ~$0.08) → **~$1/month** for one profile on the weekly schedule | Monthly cost report vs estimate; investigate if > 2× |

## 2. Runs and scheduling

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-R1 | Default schedule of an active profile | **Once a week, in the night from Friday to Saturday** (Saturday 01:30 Europe/Madrid); the schedule can be changed per profile | Scheduler config test |
| NFR-R2 | Runs are sequential | Never more than one run at a time (one browser profile, A-4) | Queue test with two profiles |
| NFR-R3 | Run duration for one profile | ≤ **90 min** (spike #3: 1.5–2.5 min per vacancy) | Run records; alert if exceeded |
| NFR-R4 | Summary email after a run | Sent ≤ **10 min** after the run ends | Timestamp check in run records |
| NFR-R5 | Packages are stored before the summary is sent | No email links to a missing package | Integration test |

## 3. Browsing limits (being a polite guest)

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-B1 | Browser is read only | No form filled or submitted; no account changes | Tool allowlist (no typing into forms, no uploads, no JavaScript from the LLM); review of agent traces |
| NFR-B2 | Search pages per source per run | ≤ **2** (≈ 50 LinkedIn results; with a weekly run, search covers the past week) | Counter per run; hard stop |
| NFR-B3 | Vacancies opened per run | ≤ **25** | Counter per run; hard stop |
| NFR-B4 | Employers researched per run | ≤ **8**, ≤ 3 pages each on job boards | Counter per run |
| NFR-B5 | Page loads per job board per day, all profiles together | ≤ **150** | Daily counter; further runs that day are skipped |
| NFR-B6 | Pace | **Random pause of 1–5 s** between browser actions, so navigation looks less like a bot; no parallel browsing | Agent trace timestamps |
| NFR-B7 | Stop conditions | Login page, authwall, CAPTCHA, "Just a moment…", restriction or unusual-activity notice → stop at once, no retries (UC-08) | Tests on recorded pages (#24) |

## 4. Availability and reliability

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-A1 | Web UI availability | Best effort on free tier, ~99% per month; cold start ≤ **10 s** acceptable | Uptime check |
| NFR-A2 | A-1 (home server) is not guaranteed | A-1 down → run *blocked*, user emailed, next slot retries; no retry loops | Test with A-1 unreachable |
| NFR-A3 | Share of scheduled runs that complete (not counting runs blocked by job boards or A-1) | ≥ **90%** | Monthly run statistics |
| NFR-A4 | Share of vacancies that fail inside a completed run | ≤ **20%** | Run statistics |
| NFR-A5 | One failing vacancy or source does not fail the run | Run continues (UC-07 A2, A4) | Tests |
| NFR-A6 | Backups of user data | Daily, kept 7 days | Restore drill once before MVP release |

## 5. Security

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-S1 | Every page and API requires authentication | 100%; MVP admits only the owner's account | Automated test of all routes without a session |
| NFR-S2 | Secrets (A-1 service token, LLM API key, email credentials) | Only in a secret manager; never in the repo, logs or images | Secret-scanning hook and CI check; log review |
| NFR-S3 | Transport security | HTTPS only, everywhere | Config check |
| NFR-S4 | Cloud access | Least-privilege service accounts; CI deploys through Workload Identity Federation, no long-lived keys | IaC review (ADR #16) |
| NFR-S5 | Secret rotation | A-1 service token and API keys rotated every **90 days** or on suspicion | Calendar reminder; rotation runbook |
| NFR-S6 | Prompt injection | Page content is data; the LLM gets no tools that can submit forms, run JavaScript or change accounts | Tool allowlist test; eval with injected vacancy text |
| NFR-S7 | Dependencies | Known high/critical vulnerabilities fail CI (pip-audit fails on any known vulnerability — stricter; non-applicable findings are ignored by ID with a reason, ADR-0005) | Dependency scan in CI |
| NFR-S8 | Job-board credentials | Never stored or typed by the system (A-2) | Code review; no credential fields in the data model |

## 6. Privacy and personal data (GDPR)

The MVP processes only the owner's own data, but it is built as if it had other users.

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-P1 | Data minimisation | Store only: account email, settings, profile files, runs, vacancies, dossiers, packages, applied registry. No copies of full job-board pages beyond what a package shows | Data model review |
| NFR-P2 | Data location | **Any region**; the region is chosen to stay within the free tier (ADRs #15, #18). Revisit if the product gets other users | IaC check |
| NFR-P3 | Retention | Packages and dossiers of vacancies not applied to: **90 days**. Applied registry and its packages: until the user deletes them (needed for the re-apply period). Run records without personal data: 12 months. Logs: **30 days**, without resume content | Scheduled cleanup job; test |
| NFR-P4 | Deletion | Deleting a profile removes its files, runs and packages within **24 h**; backups expire within 7 days | Test + backup policy |
| NFR-P5 | Data sent to the LLM provider | Only what a step needs (resume, vacancy, dossier text); provider terms checked so that API data is not used for training (ADR #19) | ADR #19; prompt review |
| NFR-P6 | Personal data in logs and traces | Resume text, phone and email are not logged; agent traces kept ≤ 30 days | Log review; test |
| NFR-P7 | Recorded pages used as test fixtures | Anonymised (names, contacts) before entering the repo; the repo is public | Review in #24; secret/PII scan in CI |

## 7. Files and inputs

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-F1 | Accepted formats | .pdf (with a text layer), .txt, .md | Upload tests |
| NFR-F2 | File size | ≤ **5 MB** per file | Upload test |
| NFR-F3 | Extraction feedback | Preview of extracted data within **30 s** of upload (UC-03) | Test |
| NFR-F4 | Generated resume PDF | ≤ 2 MB (the limit most application forms have, spike #2); text-selectable | Test |

## 8. Usability and UI

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-U1 | Responsive UI | Every page usable at **360 px** width and on desktop | Automated screenshots at 360 / 768 / 1280 px |
| NFR-U2 | Package page on a phone | Download the PDF and copy each answer with **one tap** | Manual check on a phone |
| NFR-U3 | Page speed | Main pages interactive in ≤ **3 s** on mobile 4G (excluding cold start) | Lighthouse in CI |
| NFR-U4 | Accessibility | WCAG 2.2 AA for colour contrast, labels and keyboard use | Automated accessibility check in CI |
| NFR-U5 | Language | UI in English. The tailored resume is in the language of the base resume | Test |
| NFR-U6 | User time per package | ≤ **5 min** to review and apply (vision metric) | Owner's tracking during the first month |

## 9. AI quality

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-Q1 | Invented experience in tailored resumes | **0** | Evals (#25) on every prompt or model change; reviewer agent |
| NFR-Q2 | Added skills follow the rules (critical, learnable within two weeks, skills section only, highlighted) | **100%** of added skills | Evals; reviewer agent |
| NFR-Q3 | Filtering precision | ≥ **70%** of prepared packages are applied to | Applied registry vs prepared packages, monthly |
| NFR-Q4 | Changes to prompts, models or agent configuration | Gated by evals in CI | CI rule |

## 10. Observability and operations

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-O1 | Every run is traceable | Status, counts, cost, duration, errors and skip reasons per vacancy | Run page (UC-10) |
| NFR-O2 | Alerts to the user | Email on blocked run, failed run, budget alert, restriction notice | Tests |
| NFR-O3 | Kill switch effect | Running run stops ≤ **1 min** after the switch (after the current step) | Test |

## 11. Maintainability and portability

| ID | Requirement | Target | Verification |
|---|---|---|---|
| NFR-M1 | LLM provider abstraction | Switching provider for a step is a configuration change plus an eval run, no pipeline rewrite | Code review; one step runs on two providers in tests |
| NFR-M2 | Browser access abstraction | All browsing through `BrowserGateway`; the pipeline does not call MCP directly | Code review / architecture test |
| NFR-M3 | Infrastructure as code | 100% of cloud resources created by Terraform from CI | `terraform plan` shows no drift |
| NFR-M4 | Build and test | One command each, non-zero exit on failure; CI runs both on every PR | CI |
| NFR-M5 | Tests never touch real job boards | CI uses recorded pages and a fake MCP (#24) | CI network rule / hook |

## 12. Decisions (2026-11-23)

These values close the vision's open questions:

| Question (vision §13) | Decision | NFR |
|---|---|---|
| Default schedule | Once a week, night from Friday to Saturday (Saturday 01:30 Europe/Madrid); changeable per profile | NFR-R1 |
| Browsing limits per run | 2 search pages per source, 25 vacancies, 8 employers, 150 page loads per job board per day, random 1–5 s pauses | NFR-B2…B6 |
| Retention | 90 days for packages not applied to; applied registry until deleted; logs 30 days | NFR-P3 |
| File size | 5 MB | NFR-F2 |
| Data location | Any region; free tier decides | NFR-P2 |
