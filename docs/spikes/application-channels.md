# Spike: application channels

| | |
|---|---|
| **Issue** | #4 |
| **Status** | Draft — channel census pending |
| **Date** | 2026-11-23 |
| **Sources** | Spike #2 dry-run of 4 application flows ([browser-flows.md](browser-flows.md) §4), spike #2 search data, ATS vendor documentation; channel census (scenario 05) to be added |

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

## Recommendation for MVP (draft, to be confirmed by the census)

| Tier | Channels | What the system does |
|---|---|---|
| **Automated, with approval** | LinkedIn Easy Apply | Fills the modal from profile fields and approved answers, uploads the tailored PDF, stops for approval, submits |
| **Prepared, user applies** | Single-page ATS (Ashby, Greenhouse, Lever), custom careers sites, Glassdoor / Indeed | Builds the application package — tailored resume PDF, answers to the questions found on the form, cover text — and gives the user the link; the user submits. Tracked as "prepared" in the run history |
| **Automated, when present** | Email | Sends the package via the email channel (ADR #21). Rare, so not a priority |
| **Out of scope** | Workday and any site that requires creating an account | Listed in the run results with the link only |

Why this split:

- **Easy Apply is the only channel that is both common and uniform**: one flow, no extra accounts, no CAPTCHA seen. Automating it covers roughly half of LinkedIn vacancies (to be confirmed).
- **External ATS forms differ per employer, often ask essay questions and can show a CAPTCHA.** Preparing the package gives most of the value (tailoring and answers are the hard part) without fighting each form. Automating Ashby and Greenhouse is a good post-MVP step, since they are single-page and need no account.
- **Consent checkboxes and essay answers are statements made in the user's name**, which is one more reason to keep the user in the loop for non-uniform channels.

**Impact on the vision (#5):** "send to the employer" becomes "send automatically where the channel allows (Easy Apply, email); otherwise prepare the package for one-click manual submission". The run history needs a status per vacancy: *sent*, *prepared*, *skipped (channel not supported)*.

## Channel census

<To fill from `notes/05-channel-census.md`: share of Easy Apply, external ATS by vendor, custom sites and email among ~25 LinkedIn and ~10 Glassdoor vacancies.>

| Channel | LinkedIn (n=) | Glassdoor (n=) |
|---|---|---|
| Easy Apply / quick apply | | |
| Greenhouse | | |
| Ashby | | |
| Lever | | |
| Workday | | |
| Other ATS | | |
| Custom site | | |
| Email in description | | |
