# Job Finder — Product Vision

| | |
|---|---|
| **Status** | v1 — for acceptance |
| **Owner** | ArtemenkoAndrii |
| **Issues** | #1 (draft), #5 (v1) |
| **Last updated** | 2026-11-23 (use cases #6) |
| **Based on** | Spikes [#2 browser flows](spikes/browser-flows.md), [#3 LLM cost](spikes/llm-cost.md), [#4 application channels](spikes/application-channels.md) |

## 1. Summary

Job Finder is an AI-driven assistant that finds relevant vacancies, researches employers and prepares a tailored application package for each vacancy, on a schedule. The user sets up what they are looking for once, then reviews the prepared packages and applies with a few clicks.

The project has a second, equally important goal: to practice building an AI-native product following Anthropic's [AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook) and current best practices.

## 2. Problem

Searching for a job is repetitive and time-consuming:

- the same searches have to be repeated across several job boards every few days;
- most vacancies turn out to be irrelevant (salary, location, stack), but this is only visible after reading them;
- assessing an employer (what they do, employee reviews, realistic salary, interview process) takes extra research;
- a generic resume performs worse than one adapted to the vacancy, but adapting it every time is tedious;
- application forms ask the same questions again and again (salary expectation, notice period, work permit, years of experience);
- it is easy to lose track of where and with which resume one has already applied.

## 3. Target user

**MVP:** a single user, the product owner — a software engineer actively looking for a job, comfortable with uploading structured files and reviewing AI output.

**Later (not MVP):** other job seekers. The design should not block multi-user support, but nothing is built for it now.

## 4. Goals

1. Save the user's time: the system does search, filtering, research, resume tailoring and answers to typical questions; the user spends minutes per vacancy on review and submission.
2. Increase relevance: only vacancies matching the user's criteria reach the user.
3. Increase quality of applications: every resume is tailored to the vacancy and reviewed by a second agent.
4. Keep full transparency: for every vacancy the user can see the dossier, the exact resume and answers prepared, where to apply and what happened to it.
5. Learning goal: build and run the product as an AI factory — intent → spec → plan → execution with agents, evals and human gates.

## 5. Non-goals (MVP)

- **Submitting applications** — the user always applies manually (decision in spike #4; automation is post-MVP, #32).
- Multi-user support, billing, onboarding of other users.
- Follow-up messages, chatting with recruiters.
- Interview preparation and scheduling (beyond the interview notes in the dossier).
- Native mobile apps (a responsive web UI is enough).
- Guaranteed compliance with job boards' terms of service (see risks).

## 6. Success metrics

| Metric | Target |
|---|---|
| Relevant vacancies surfaced per week (per active profile) | ≥ 10 |
| Filtering precision: share of prepared packages the user applies with | ≥ 70% |
| Packages prepared per week | ≥ 5 |
| Invented experience, roles, dates or achievements in tailored resumes | 0 — any case is a defect |
| Added skills not highlighted to the user | 0 — any case is a defect |
| User time per package (review + manual submission) | ≤ 5 min |
| Response rate from employers | Tracked; baseline to be established |
| Infrastructure cost per month | ≤ $5 |
| LLM cost per month | ≤ $10 (cap); expected ~$2–4 for one profile (spike #3) |

## 7. How it works

For each active search profile, on a schedule:

1. **Search** vacancies in the sources: LinkedIn and Glassdoor.
2. **Deduplicate** against previously processed vacancies.
3. **Hard-filter** obvious mismatches: salary below expectations, wrong location or work format, stack too far from the user's, blacklisted companies.
4. **Research the employer** on LinkedIn and Glassdoor and build a short dossier: what the company does, rating, pros and cons from reviews, salary levels, interview difficulty and questions.
5. **Re-filter** using the dossier (e.g. the realistic salary turns out to be too low).
6. **Tailor a resume** for each remaining vacancy, based on the user's resume and configured rules. Critical missing skills may be added under the rules in section 9; each addition is highlighted.
7. **Review** each tailored resume by a separate reviewer agent; send it back for rework if a rule is violated.
8. **Prepare the application package**: tailored resume (PDF), dossier, answers to typical screening questions from the profile, a short cover note, the link and the channel.
9. **Report** — the user receives a summary email with the prepared packages.
10. **Apply manually** — the user opens a package, reviews it, applies on the employer's channel and marks the vacancy as applied or skipped.

The browser is used **read only**: the system searches and reads vacancies and employer pages; it never fills in or submits forms.

## 8. MVP scope

### User experience

0. The user signs in and provides an email address for notifications.
1. The user lands on a personal page and uploads a resume (.pdf, .txt, .md) and a vacancy requirements file (.pdf, .txt, .md): stack, expected salary, office location or remote, etc.
2. Each resume + requirements pair is a **search profile**; the user can have up to 3.
3. A search profile can be created, activated, deactivated and deleted.
4. Vacancies and employer information come from **LinkedIn and Glassdoor**.
5. For each profile the user sees the history of runs: date, vacancies found, packages prepared, vacancies applied to.
6. Clicking a run opens a table of vacancies; each row opens the **application package**: dossier, tailored resume (PDF, added skills highlighted), answers, cover note, link and channel, and the vacancy status (*prepared*, *applied*, *skipped*, *skipped by filter*, *failed*).
6a. **Run now:** the user can start a run of any profile by hand, in addition to the schedule.

### Added to the original scope

7. **Application data:** answers to typical form questions come from the two profile files. Contacts (phone, email, LinkedIn, current location, languages) are taken from the **resume**; what a resume usually lacks — work permit / visa sponsorship, notice period, relocation willingness, salary range — is written in the **requirements file**.
8. **Added-skill highlighting:** every skill added to a tailored resume is highlighted, with a short note on what to learn before the interview; the user can reject it.
9. **Company blacklist:** companies that are always skipped (e.g. the current employer), listed in the requirements file.
10. **Browsing limits:** maximum number of vacancies and pages opened per run, to stay a polite guest on the job boards.
11. **Kill switch:** one action stops all runs immediately.
12. **Summary email** after each run, listing the prepared packages.

### Out of scope for MVP

- Submitting applications on any channel (Easy Apply, ATS forms, email) — post-MVP, #32.
- Reading the actual questions of each application form (they appear only after opening the form, which is an action in the user's account); the package answers typical questions instead.
- Sources other than LinkedIn and Glassdoor.
- Editing tailored resumes inside the app (the user can reject and re-generate).

## 9. Product principles

- **Human in the loop.** The system prepares, the user decides and submits.
- **Never invent experience.** A tailored resume may reorder, emphasize and rephrase, but never add roles, projects, achievements, dates or years of experience that are not in the source resume.
- **Learnable skills only, always highlighted.** A skill missing from the source resume may be added only if all of the following hold:
  - it is critical for the vacancy (required or strongly preferred);
  - the user can realistically learn it at an overview level within a couple of days before an interview;
  - it is listed as a skill only, not attributed to a past role, project or achievement;
  - it is highlighted to the user, with a short note on what to learn, and can be rejected.
- **Read only, and a polite guest.** The browser only reads; it respects browsing limits, acts slowly and stops immediately on a CAPTCHA, login page or any sign of account restriction.
- **Everything is traceable.** Every package can be traced back to the vacancy, the dossier, the exact resume and answers, and the channel.
- **Personal data stays minimal.** Resumes and profile data are personal; store only what is needed, and allow deleting it.

## 10. Constraints

- **Hosting budget:** up to $5/month for hosting and infrastructure.
- **LLM budget:** separate from hosting; **cap $10/month**, alert at $5. Spike #3 estimated ~$0.13 per run of one profile.
- **Hosting:** cloud, free tier or minimal cost. GCP is preferred (account exists); other providers and combinations may be considered.
- **Models:** runtime agents use **OpenAI models** (API balance available) — GPT-6 Luna for browsing, extraction, filtering and tailoring; GPT-6.2 Sol for resume review (spike #3, to be confirmed by evals). The design keeps a provider abstraction. Claude Code is the development tool.
- **UI:** simple web UI, responsive for laptop and mobile browsers.
- **Authentication:** as simple as possible to implement, but reliable enough for an early-stage product.
- **Team:** one developer working part-time, with AI agents.

## 11. Assumptions

- **A-1. Browser MCP endpoint.** A Playwright MCP server with LinkedIn and Glassdoor sessions (persistent browser profile) is available over HTTPS behind Cloudflare Access with service-token authentication. Building and operating it is out of scope of this project. The endpoint URL and token are configuration secrets and are not stored in the repository.
- **A-2. Manual login.** Job-board sessions on A-1 are logged in manually by the user, with the user's own accounts. The system never handles job-board passwords; an expired session stops the run and asks the user to log in again.
- **A-3.** The user provides a resume and requirements in readable form (.pdf, .txt, .md).
- **A-4.** One browser profile serves all runs, so runs are executed sequentially.
- **A-5.** The Glassdoor account on A-1 has contributed a review or salary, so reviews and salaries are not hidden behind the give-to-get wall (spike #2 saw the wall on another session; to be verified).

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Job board account restricted or banned (automation against ToS) | High — loss of a key job-search channel | **Accepted risk**, reduced in the MVP: read-only browsing, browsing limits, sequential runs, auto-stop on any warning or challenge |
| Glassdoor bot protection (Cloudflare challenge blocked 2 of 3 attempts in spike #2) | Medium — no Glassdoor data in a run | Treat as a normal stop condition; the run continues with LinkedIn only |
| Unstable browser sessions when the agent runs through OpenAI's hosted MCP (pages going blank in spike #3) | High — runs fail | Shared browser context on A-1 first; otherwise run the agent loop in our code with one MCP session (#19, #20) |
| LLM cost higher than expected | Low — measured in spike #3 | $10/month cap and alert, per-run cost tracking |
| Tailored resume contains invented experience, or an added skill the user cannot back up in an interview | High — reputational | Rules in section 9, reviewer agent, evals, highlighting, manual submission |
| Prompt injection via vacancy text | Medium — the agent has a logged-in browser | Read-only browsing, restricted browser tools, no submission |
| Job board UI changes break flows | Medium | AI-driven navigation, contract checks, failure alerts |
| Home server (A-1) unavailable or session expired | Medium — runs blocked | Detect and report, no retry loops |
| Summary emails land in spam | Low | Proper sending setup (ADR) |
| Personal data leak | High | Minimal storage, secrets management, access control |

## 13. Open questions

1. Are "direct referrals" and general web search (e.g. Google) sources for a later version?
2. How often should runs be scheduled by default (daily, several times a week)?
3. How long are runs, dossiers and packages retained?
4. What are the default browsing limits per run?

Answered: LLM cap ($10/month, #3); which channels can be automated and what the MVP does (prepare packages, manual submission, #4); where application data and tailoring rules live (the two profile files; fixed system rules plus per-profile tailoring notes — [use cases](requirements/use-cases.md) #6).

## 14. Glossary

| Term | Meaning |
|---|---|
| **Search profile** | A base resume + requirements file pair with its own schedule and history; up to 3 per user |
| **Requirements file** | What the user is looking for — positions, stack, salary range, location / work type, excluded companies — plus data a resume lacks (work permit, notice period, relocation) and optional tailoring notes |
| **Application data** | Answers to typical form questions, taken from the resume (contacts) and the requirements file (salary, work permit, notice period, …) |
| **Run** | One execution of the pipeline for one search profile |
| **Source** | Where vacancies and employer information come from; MVP: LinkedIn and Glassdoor |
| **Vacancy** | A job posting found in a source |
| **Dossier** | Short employer research attached to a vacancy |
| **Tailored resume** | Resume adapted to a specific vacancy |
| **Added skill** | A skill not present in the source resume, added under the rules in section 9; always highlighted to the user |
| **Application package** | Everything the user needs to apply to one vacancy: tailored resume (PDF), dossier, answers, cover note, link and channel |
| **Channel** | How one applies to a vacancy, chosen by the employer: LinkedIn Easy Apply, Glassdoor quick apply, employer ATS or careers site, email |
| **Vacancy status** | *prepared* (package ready), *applied* (marked by the user), *skipped* (by the user), *skipped by filter*, *failed* (page could not be processed) |
| **Kill switch** | A single action that stops all runs |
| **A-1** | The external Browser MCP endpoint (see Assumptions) |

## 15. References

- [The AI-native SDLC playbook](https://claude.com/resources/articles/the-ai-native-sdlc-playbook)
- [Use cases and story map](requirements/use-cases.md)
- Spikes: [browser flows](spikes/browser-flows.md), [LLM cost](spikes/llm-cost.md), [application channels](spikes/application-channels.md)
- Roadmap: GitHub milestones P0–P5
