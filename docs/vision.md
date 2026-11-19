# Job Finder — Product Vision

| | |
|---|---|
| **Status** | Draft |
| **Owner** | ArtemenkoAndrii |
| **Issue** | #1 |
| **Last updated** | 2026-11-19 |

## 1. Summary

Job Finder is an AI-driven assistant that finds relevant vacancies, researches employers, tailors a resume for each vacancy and sends applications on the user's behalf, on a schedule. The user sets up what they are looking for once and then only reviews, approves and follows the results.

The project has a second, equally important goal: to practice building an AI-native product following Anthropic's [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) and current best practices.

## 2. Problem

Searching for a job is repetitive and time-consuming:

- the same searches have to be repeated across several job boards every few days;
- most vacancies turn out to be irrelevant (salary, location, stack), but this is only visible after reading them;
- assessing an employer (what they do, employee reviews, realistic salary, interview process) takes extra research;
- a generic resume performs worse than one adapted to the vacancy, but adapting it every time is tedious;
- it is easy to lose track of where and with which resume one has already applied.

## 3. Target user

**MVP:** a single user, the product owner — a software engineer actively looking for a job, comfortable with uploading structured files and reviewing AI output.

**Later (not MVP):** other job seekers. The design should not block multi-user support, but nothing is built for it now.

## 4. Goals

1. Save the user's time: the system does search, filtering, research and resume tailoring; the user spends minutes per week on review and approval.
2. Increase relevance: only vacancies matching the user's criteria reach the user.
3. Increase quality of applications: every resume is tailored to the vacancy and reviewed by a second agent.
4. Keep full transparency: for every application the user can see the vacancy, the employer dossier, the exact resume sent and how it was sent.
5. Learning goal: build and run the product as an AI factory — intent → spec → plan → execution with agents, evals and human gates.

## 5. Non-goals (MVP)

- Multi-user support, billing, onboarding of other users.
- Cover letters, follow-up messages, chatting with recruiters.
- Interview preparation and scheduling.
- Native mobile apps (a responsive web UI is enough).
- Fully unattended sending as the default mode (see principles below).
- Guaranteed compliance with job boards' terms of service (see risks).

## 6. Success metrics

Targets are initial guesses and will be revisited after the feasibility spikes (#2–#4).

| Metric | Initial target |
|---|---|
| Relevant vacancies surfaced per week (per active profile) | ≥ 10 |
| Filtering precision: share of surfaced vacancies the user approves | ≥ 70% |
| Applications sent per week | ≥ 5 |
| Invented facts in tailored resumes (skills, experience, dates) | 0 — any case is a defect |
| User time spent per week on review and approval | ≤ 30 min |
| Response rate from employers | Tracked; baseline to be established |
| Cost per run and per month | Within budget (section 10) |

## 7. How it works

For each active search profile, on a schedule:

1. **Search** vacancies in configured sources.
2. **Deduplicate** against previously processed vacancies.
3. **Hard-filter** obvious mismatches: salary below expectations, wrong location or work format, stack too far from the user's.
4. **Research the employer** and build a short dossier: what the company does, employee reviews, expected salary, typical interview questions.
5. **Re-filter** using the dossier (e.g. the realistic salary turns out to be too low).
6. **Tailor a resume** for each remaining vacancy, based on the user's resume and configured rules.
7. **Review** each tailored resume by a separate reviewer agent; send it back for rework if needed.
8. **Approve** — the user reviews and approves applications (MVP default).
9. **Send** the application through the appropriate channel (job board form, email, employer site).
10. **Report** — the user receives a short summary of sent applications and companies.

## 8. MVP scope

### User experience

0. The user signs in and provides an email address for notifications.
1. The user lands on a personal page and uploads a resume (.pdf, .txt, .md) and a vacancy requirements file (.pdf, .txt, .md): stack, expected salary, office location or remote, etc.
2. Each resume + requirements pair is a **search profile**; the user can have up to 3.
3. A search profile can be created, activated, deactivated and deleted.
4. For each profile the user sees the history of runs: date, vacancies found, applications sent.
5. Clicking a run opens a page with a table of vacancies: short dossier, copy of the sent resume, and the sending channel (email, employer site form, etc.).

### Added to the original scope

6. **Approval before sending:** applications wait for the user's approval; auto-send is a later option.
7. **Company blacklist:** companies that must never receive an application (e.g. the current employer).
8. **Daily limits:** maximum number of applications and browser actions per day.
9. **Kill switch:** one action stops all runs and sending immediately.
10. **Summary email** after each run.

### Out of scope for MVP

- More than one job source in the first delivery slice (LinkedIn first, Glassdoor later).
- Automatic sending without approval.
- Editing tailored resumes inside the app (the user can reject and re-generate).

## 9. Product principles

- **Human in the loop.** The system prepares, the user decides. Nothing is sent without approval in MVP.
- **Never invent facts.** A tailored resume may reorder, emphasize and rephrase, but never add skills, experience or dates that are not in the source resume.
- **Be a polite guest.** Respect rate limits, act slowly, stop immediately on any sign of account restriction.
- **Everything is traceable.** Every application can be traced back to the vacancy, the dossier, the exact resume and the channel.
- **Personal data stays minimal.** Resumes contain personal data; store only what is needed, and allow deleting it.

## 10. Constraints

- **Budget:** up to $5/month for everything (original goal). Spike #3 will show whether LLM usage fits into this; if not, the budget will be split into infrastructure (≤ $5/month) and an explicit LLM cap.
- **Hosting:** cloud, free tier or minimal cost. GCP is preferred (account exists); other providers and combinations may be considered.
- **Models:** Claude models initially, chosen per task; the provider may change in the future, so the design must not be locked to one vendor.
- **UI:** simple web UI, responsive for laptop and mobile browsers.
- **Authentication:** as simple as possible to implement, but reliable enough for an early-stage product.
- **Team:** one developer working part-time, with AI agents.

## 11. Assumptions

- **A-1. Browser MCP endpoint.** A Playwright MCP server with logged-in LinkedIn and Glassdoor sessions (persistent browser profile) is available over HTTPS behind Cloudflare Access with service-token authentication. Building and operating it is out of scope of this project. The endpoint URL and token are configuration secrets and are not stored in the repository.
- **A-2.** The user's own accounts are used for job boards.
- **A-3.** The user provides a resume and requirements in readable form (.pdf, .txt, .md).
- **A-4.** One browser profile serves all runs, so runs are executed sequentially.

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Job board account restricted or banned (automation against ToS) | High — loss of a key job-search channel | **Accepted risk.** Low volume, limits, auto-stop on any warning or challenge, prefer applying via email / employer site |
| LLM cost exceeds budget | Medium | Measure in spike #3; deterministic steps where possible; per-run cost tracking |
| Tailored resume contains invented facts | High — reputational | Reviewer agent, evals, manual approval |
| Prompt injection via vacancy text | High — agent acts with a logged-in browser | Separate reading and sending, restricted browser tools, approval before sending |
| Job board UI changes break flows | Medium | AI-driven navigation, contract checks, failure alerts |
| Home server (A-1) unavailable | Medium — runs blocked | Detect and report, no retry loops |
| Emails land in spam | Medium | Proper sending setup (decided in ADR) |
| Personal data leak | High | Minimal storage, secrets management, access control |

## 13. Open questions

1. Does the $5/month budget include LLM usage, or only infrastructure? (spike #3)
2. Which application channels can be automated reliably: Easy Apply, email, employer sites? (spike #4)
3. Are "direct referrals" and general web search (e.g. Google) real sources for MVP, or later?
4. Where do resume tailoring rules live: inside the requirements file, or as separate per-profile settings?
5. How often should runs be scheduled by default (daily, several times a week)?
6. How long are runs, dossiers and sent resumes retained?
7. What are the default daily limits for applications and browser actions?

## 14. Glossary

| Term | Meaning |
|---|---|
| **Search profile** | A resume + requirements pair with its own schedule and history; up to 3 per user |
| **Requirements file** | User's criteria for vacancies: stack, salary, location / remote, etc. |
| **Run** | One execution of the pipeline for one search profile |
| **Vacancy** | A job posting found in a source |
| **Source** | Where vacancies come from: LinkedIn, Glassdoor, etc. |
| **Dossier** | Short employer research attached to a vacancy |
| **Tailored resume** | Resume adapted to a specific vacancy |
| **Application** | A tailored resume sent (or prepared to be sent) to an employer |
| **Channel** | How an application is sent: job board form, email, employer site |
| **Approval** | The user's confirmation that an application may be sent |
| **Kill switch** | A single action that stops all runs and sending |
| **A-1** | The external Browser MCP endpoint (see Assumptions) |

## 15. References

- [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)
- Roadmap: GitHub milestones P0–P5 and issues #1–#34
