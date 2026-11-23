# Spike: application channels

| | |
|---|---|
| **Issue** | #4 |
| **Status** | Done — decision taken 2026-11-23 |
| **Date** | 2026-11-23 |
| **Sources** | Spike #2 dry-run of 4 application flows ([browser-flows.md](browser-flows.md) §4), spike #2 search data, ATS vendor documentation |

## Goal

Find out which ways of applying can be automated, with what effort and risk, and which ones the MVP should support.

## Channels seen

| Channel | Where it comes from | Seen in spike #2 |
|---|---|---|
| **LinkedIn Easy Apply** | "Easy Apply" button on LinkedIn | 2 flows walked; ~14 of 25 cards on a results page had the label |
| **External ATS** (Greenhouse, Ashby, Lever, Workday, …) | "Apply on company website" on LinkedIn | Ashby walked; Greenhouse and a custom careers site seen as targets |
| **Glassdoor quick apply → Indeed Smart Apply** | "Solicitud rápida" on Glassdoor | 1 flow walked |
| **Custom careers site** | "Apply on company website" | Seen as a target (SD Worx), not walked |
| **Email** | Address in the vacancy text | **Not seen** on any vacancy |

## Evaluation per channel

| | LinkedIn Easy Apply | Single-page ATS (Ashby, Greenhouse, Lever-type) | Workday | Glassdoor → Indeed Smart Apply | Custom careers site | Email |
|---|---|---|---|---|---|---|
| **Account needed** | No (uses the LinkedIn session on A-1) | No | **Yes — a separate account per employer** | Indeed account | Varies | No |
| **Steps** | 4 pages in a modal | 1 page | Many, multi-page | ~5–7 (progress 14% after step 1) | Varies | 1 |
| **Typical fields** | Contact, phone, resume, 0–11 screening questions, privacy consent | Name, email, resume, LinkedIn URL, notice period, salary, location, free-text questions | Full profile re-entry, work history, questions | Contact, phone, then unknown | Unknown | Subject, body, attachment |
| **Free-text questions** | Some | **Often long and essay-like** (3 in the Ashby example) | Yes | Unknown | Unknown | Cover text |
| **Resume upload** | Yes, DOC/DOCX/PDF < 2 MB | Yes | Yes | Not reached | Usually | Attachment |
| **Bot protection** | Authwall seen once; account-level risk | Greenhouse uses invisible reCAPTCHA with a visible fallback challenge | Varies by tenant | Invisible reCAPTCHA observed | Varies | None for us; deliverability matters |
| **Risk if it goes wrong** | **LinkedIn account restriction** (key job-search channel) | Application rejected as spam; no account risk | Abandoned accounts | Indeed account restriction | Low | Spam folder |
| **Automation feasibility** | **High** — one known flow | **Medium** — simple pages, but long free-text answers and CAPTCHA fallback | **Low** — account creation per employer | **Low/Medium** — separate account, reCAPTCHA, flow not fully seen | **Low** — every site differs | **High**, but rare |

Notes:

- Greenhouse documents that its job boards use Google's invisible reCAPTCHA, which analyses mouse movements and typing; if a submission fails it, a visible captcha test is shown. An agent cannot be expected to pass that fallback.
- Workday requires a candidate account to apply, and each employer runs its own portal, so a new account per employer is the common case. This alone rules Workday out for automation.
- Easy Apply on LinkedIn can still route to the employer's ATS behind the scenes (spike #2: `applicantTrackingSystemName=Greenhouse`) while the whole flow stays in the LinkedIn modal — for us it is Easy Apply.

## Requirements common to all channels

Every channel that got past step 1 asked for data a resume does not contain. These become **search profile fields** (input for vision #5 and use cases #6):

- phone number (required by 2 of 4 flows on step 1);
- resume file in DOC/DOCX/PDF under 2 MB — the tailored resume must be rendered to PDF and delivered to the browser on A-1 (ADR #18);
- salary expectation, notice period, current location, relocation willingness;
- work permit and visa sponsorship status;
- LinkedIn profile URL;
- years of experience per technology (often as select ranges: 0–2, 3–4, 5–7, 8+);
- language levels;
- consent to the employer's privacy policy (a checkbox — must be the user's decision; see below).

**Screening answers:** structured questions (selects, yes/no) can be answered from profile fields; free-text questions need the LLM and the user's approval. The approval screen must show every answer, not only the resume.

## Decision for MVP (2026-11-23)

**Sources vs channels.** LinkedIn and Glassdoor are the **sources**: where the system finds vacancies and employer information (reviews, pros and cons, salary levels, interview difficulty). A **channel** is how one applies to a particular vacancy, and it is chosen by the employer: Easy Apply / Glassdoor quick apply inside the platform, or a redirect to the employer's ATS or careers site.

**In the MVP the system never submits applications.** For every vacancy that passes all filters it prepares an **application package**, and the user always applies manually:

| Package item | Content |
|---|---|
| Tailored resume | PDF, built under the vision rules (no invented experience, added skills highlighted) and approved by the reviewer agent |
| Employer dossier | What the company does, rating, pros and cons, salary levels, interview difficulty and questions (LinkedIn, Glassdoor) |
| Answers | Answers to the typical screening questions, built from profile fields (phone, salary expectation, notice period, work permit, location, years per technology, languages) plus a short cover note |
| Link and channel | Where to apply, and how: Easy Apply, Glassdoor quick apply, employer ATS (vendor) or careers site |

The run history shows a status per vacancy, for example *prepared*, *applied* (marked by the user), *skipped*.

**Why:**

- One flow for every channel: no per-ATS forms, CAPTCHAs, account creation (Workday) or essay answers submitted in the user's name without review.
- **No account risk from submissions** — the browser only reads.
- **Resume upload to A-1 is not needed in the MVP**: the PDF goes to the user, not into a browser form (relaxes ADR #18).
- The value of the product — finding, filtering, researching, tailoring — is kept; the manual step is a few clicks per vacancy.

**Not in the MVP:** reading the actual questions of each application form. Easy Apply questions appear only after opening the form (spike #2), which is an interaction with the user's account; answers to typical questions cover most of them. Revisit together with automated sending.

**Post-MVP options** (for the review in #38 and the auto-send slice #32):

| Next step | Why first |
|---|---|
| Automate LinkedIn Easy Apply (with approval) | Common and uniform; no extra accounts |
| Automate single-page ATS (Ashby, Greenhouse, Lever) | No account; but long free-text questions and a CAPTCHA fallback |
| Email channel | Trivial, but rare |
| Workday, sites requiring an account | Keep manual |

A channel census (`spikes/browser-flows/prompts/05-channel-census.md`, read-only) is ready for when automated sending is reconsidered; it measures how often each channel occurs. It is not needed for the MVP decision.
