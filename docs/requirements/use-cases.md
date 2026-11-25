# Use cases and story map (MVP)

| | |
|---|---|
| **Issue** | #6 |
| **Status** | For acceptance |
| **Based on** | [Vision v1](../vision.md) |
| **Last updated** | 2026-11-23 |

## 1. Actors

| Actor | Kind | Role |
|---|---|---|
| **User** | Person | The job seeker (MVP: the product owner). Sets up profiles, reviews packages, applies manually |
| **Scheduler** | System | Starts runs of active profiles on their schedule |
| **Job Finder** | System | Runs the pipeline: search, filter, research, tailor, review, prepare packages, notify |
| **Browser (A-1)** | External system | Remote browser with the user's LinkedIn and Glassdoor sessions, behind Cloudflare Access |
| **Job boards** | External system | LinkedIn and Glassdoor, reached only through A-1, read only |
| **Other dossier sources** | External system | Company websites (through A-1) and web search (news, salary and review sites); more can be added later |
| **LLM provider** | External system | OpenAI models for agents |
| **Email service** | External system | Delivers summary and alert emails |

## 2. Use case overview

| ID | Use case | Primary actor | Slice |
|---|---|---|---|
| UC-01 | Sign in | User | Skeleton #22 |
| UC-02 | Manage settings | User | S1 #26 |
| UC-03 | Create a search profile | User | S1 #26 |
| UC-04 | Edit, activate, deactivate or delete a profile | User | S1 #26 |
| UC-05 | Run a profile now | User | S2 #27 |
| UC-06 | Run a profile on schedule | Scheduler | S6 #31 |
| UC-07 | Execute a run (pipeline) | Job Finder | S2–S5 #27–#30 |
| UC-08 | Handle a blocked run | Job Finder, User | S2 #27 |
| UC-09 | Receive the run summary | User | S5 #30 |
| UC-10 | View run history and run details | User | S6 #31 |
| UC-11 | Review an application package | User | S5 #30 |
| UC-12 | Reject an added skill | User | S5 #30 |
| UC-13 | Mark a vacancy as applied or skipped | User | S5 #30 |
| UC-14 | Stop all runs (kill switch) | User | S6 #31 |
| UC-15 | View the applied registry | User | S5 #30 |

## 3. Use cases

### UC-01 Sign in

- **Actor:** User. **Trigger:** opens the web app.
- **Main flow:**
  1. The user signs in with their Google account through Identity-Aware Proxy ([ADR-0008](../adr/0008-user-authentication.md)).
  2. On first sign-in the system creates the user record and takes the sign-in email as the notification email.
  3. The user lands on the profiles page.
- **Alternative flows:**
  - A1. Sign-in fails or is cancelled → the user stays on Google's sign-in page.
  - A2. The account is not the allowed owner account (MVP is single-user) → IAP shows "access denied"; if IAP were bypassed, the app answers 403.
- **Result:** an authenticated session on desktop or mobile.

### UC-02 Manage settings

- **Actor:** User. **Precondition:** signed in.
- **Main flow:** the user opens Settings and changes:
  - the notification email;
  - the **re-apply period** — after how many days a vacancy the user has applied to may appear in results again (default **90 days**).
- **Alternative flows:** A1. Invalid email or a period below 1 day → field error, nothing saved.
  - A2. A new notification email must also be verified as a destination address in Cloudflare before mail reaches it ([ADR-0010](../adr/0010-email-delivery.md)); the page says so.
- **Result:** summaries and alerts go to the chosen address; the applied registry (UC-15) uses the chosen period.

All job-search data lives in the two files of each profile (UC-03), as in the vision.

### UC-03 Create a search profile

- **Actor:** User. **Precondition:** signed in, fewer than 3 profiles.
- **Main flow:**
  1. The user clicks "New profile" and gives it a name.
  2. Uploads the **base resume** (.pdf, .txt, .md). It is the source for tailoring **and** for contact data in answers: name, phone, email, LinkedIn URL, current location, languages.
  3. Uploads the **requirements file** (.pdf, .txt, .md) — what the user is looking for, plus what a resume usually does not contain:
     - positions (e.g. Lead Backend (Java), Solution Architect), stack, seniority;
     - salary range (from–to);
     - work type and location (remote, hybrid, city);
     - companies to exclude (e.g. the current employer);
     - work permit / visa sponsorship, notice period, relocation willingness;
     - optional tailoring notes (e.g. "emphasize Kotlin") and overrides (e.g. years with a technology).
  4. The system extracts both files and shows a short preview — contacts from the resume; positions, salary, location and exclusions from the requirements — so the user can see they were read correctly.
  5. The user saves; the profile is created **inactive**.
- **Alternative flows:**
  - A1. Already 3 profiles → "New profile" is disabled with an explanation.
  - A2. Unsupported format, empty or unreadable file (e.g. scanned PDF) → error, nothing saved.
  - A3. File too large (limit set in NFR #7) → error.
  - A4. The preview is wrong → the user replaces the file before saving.
- **Result:** an inactive profile ready to run.

### UC-04 Edit, activate, deactivate or delete a profile

- **Actor:** User.
- **Main flow (activate):** the user activates a profile → it is included in scheduled runs (UC-06).
- **Alternative flows:**
  - A1. Deactivate → no new scheduled runs; history and packages stay.
  - A2. Replace the resume or requirements file → applies to future runs only; existing packages keep the resume they were built with.
  - A3. Delete → confirmation; the profile, its files, runs and packages are deleted (personal data principle). A running run of this profile is stopped first.
- **Result:** profile state changed.

### UC-05 Run a profile now

- **Actor:** User. **Precondition:** the profile exists (active or not).
- **Main flow:**
  1. The user clicks "Run now".
  2. The system queues a run (UC-07) and shows it as *queued* / *running* in the history.
- **Alternative flows:**
  - A1. Another run is in progress → this run waits in the queue (one browser profile, runs are sequential).
  - A2. Kill switch is on → "Run now" is disabled.
- **Result:** a run is executed. Needed from S2 on, before the scheduler exists, and later for testing.

### UC-06 Run a profile on schedule

- **Actor:** Scheduler.
- **Main flow:** at the scheduled time the scheduler queues a run (UC-07) for every active profile, one after another.
- **Alternative flows:**
  - A1. The previous run of the profile is still running → skip this slot.
  - A2. Kill switch is on → nothing is queued.
- **Result:** runs happen without the user. The default frequency is an NFR (#7).

### UC-07 Execute a run (pipeline)

- **Actor:** Job Finder. **Precondition:** a queued run; A-1 reachable.
- **Main flow:**
  1. **Search** LinkedIn and Glassdoor with the profile's criteria, within the browsing limits.
  2. **Deduplicate**:
     - drop vacancies listed in the **applied registry** (UC-15) within the re-apply period — for every profile, not only the one that applied;
     - drop vacancies already processed for this profile in earlier runs;
     - merge the same vacancy found on both sources.
  3. **Hard-filter**: salary, location, work type, stack, excluded companies. Rejected vacancies are kept with the reason (*skipped by filter*).
  4. **Research** each remaining employer: one dossier per company per run, built from the **dossier sources**: LinkedIn, Glassdoor, the company's own website (through A-1) and web search (news, salary and review sites, through the LLM provider's search tool); more can be added later. Every fact keeps a link to its source.
  5. **Re-filter** with the dossier.
  6. **Tailor** the resume for each remaining vacancy under the rules of vision §9: reorder, emphasise and rephrase the base resume; never invent experience. A skill missing from the base resume may be added **only if** it is critical for the vacancy (required or strongly preferred) **and** the user can learn it at an overview level **within two weeks**; it goes only into the skills section, is highlighted and comes with a "what to learn" note.
  7. **Review** each tailored resume; on "rework" tailor again (max 2 rounds), then keep the best version with the reviewer's issues attached.
  8. **Prepare the package**: resume PDF, dossier, answers from settings and profile, cover note, link and channel. Status *prepared*.
  9. Record run statistics and cost; send the summary (UC-09).
- **Alternative flows:**
  - A1. Nothing found or everything filtered out → the run completes with zero packages; the summary says so.
  - A2. A single vacancy or employer page fails (page did not load, unknown layout) → that vacancy is marked *failed* with the reason; the run continues.
  - A3. Session expired, CAPTCHA, Cloudflare challenge or restriction notice → **blocked run**, UC-08.
  - A4. One source blocked or unavailable (e.g. Glassdoor challenge) → continue with the other sources; the dossier marks what is missing.
  - A5. LLM cost cap reached → stop before the next LLM step; run status *stopped: budget*; the user is alerted.
  - A6. Kill switch turned on during the run → stop after the current step; status *stopped*.
- **Result:** packages for matching vacancies and a complete record of what was skipped, failed and why.

### UC-08 Handle a blocked run

- **Actors:** Job Finder, User.
- **Main flow:**
  1. The browser shows a login page, authwall, CAPTCHA, challenge or restriction notice — or A-1 is unreachable.
  2. Job Finder stops browsing immediately (no retries), keeps what it already processed, sets status *blocked: <reason>* and emails the user.
  3. The user fixes the cause (e.g. logs in again on A-1 manually) and clicks "Resume run" or waits for the next scheduled run.
- **Alternative flows:**
  - A1. Restriction or "unusual activity" notice → also pause the schedule for that job board until the user re-enables it.
- **Result:** no repeated hits on a job board that is pushing back.

### UC-09 Receive the run summary

- **Actor:** User.
- **Main flow:** after each run with at least one package, the user gets an email: profile, run date, vacancies found / filtered / prepared, and per package the title, company, channel and a link to the package page.
- **Alternative flows:**
  - A1. Run with zero packages → no email (visible in history only). *A blocked run always emails (UC-08).*
- **Result:** the user knows there is something to review without opening the app.

### UC-10 View run history and run details

- **Actor:** User.
- **Main flow:**
  1. The user opens a profile → list of runs: date, status, vacancies found, packages prepared, vacancies applied to, cost.
  2. Opens a run → table of vacancies: title, company, source, channel, status (*prepared, applied, skipped, skipped by filter, failed*) and the reason for skips and failures.
- **Result:** full traceability of every run.

### UC-11 Review an application package

- **Actor:** User.
- **Main flow:**
  1. The user opens a package (from the run table or the summary email).
  2. Sees the vacancy summary, the dossier, the tailored resume with added skills highlighted and "what to learn" notes, the answers to typical questions, the cover note, the reviewer's remaining notes, and the link with the channel.
  3. Downloads the resume PDF and copies answers as needed.
  4. Opens the link and applies on the employer's channel (outside Job Finder).
- **Alternative flows:**
  - A1. An answer needs data that is in neither file (e.g. notice period) → shown as "add to the requirements file"; after the file is updated, answers are regenerated without re-tailoring.
- **Result:** everything needed to apply in a few minutes, on desktop or mobile.

### UC-12 Reject an added skill

- **Actor:** User. **Precondition:** the package has added skills.
- **Main flow:**
  1. The user rejects one or more added skills.
  2. The system regenerates the resume without them, reviews it again and updates the package.
- **Alternative flows:**
  - A1. The user rejects the whole resume → regenerate once; if still rejected, mark the vacancy *skipped*.
- **Result:** the resume contains only skills the user is ready to defend.

### UC-13 Mark a vacancy as applied or skipped

- **Actor:** User.
- **Main flow:**
  1. The user downloads the resume PDF, applies on the employer's channel and marks the vacancy *applied*.
  2. The system records the date and adds an entry to the **applied registry** (UC-15): the same data as in the run history — position, company, source and link, channel, profile, run, date applied, and the resume and answers that were used.
- **Alternative flows:**
  - A1. The user marks the vacancy *skipped*, with an optional reason → no registry entry.
  - A2. The user marked *applied* by mistake → undo removes the registry entry.
- **Result:** run history counts applications; the vacancy will not come back in any profile during the re-apply period.

### UC-14 Stop all runs (kill switch)

- **Actor:** User.
- **Main flow:** the user turns on the kill switch → the running run stops after the current step, queued runs are dropped, no new runs start.
- **Alternative flows:** A1. Turning the kill switch off → scheduled runs resume from the next slot.
- **Result:** the system stops touching the job boards immediately.

### UC-15 View the applied registry

- **Actor:** User.
- **Main flow:**
  1. The user opens "Applied" — one list for all profiles.
  2. Each entry shows position, company, source and link, channel, profile, date applied, and opens the package that was used (resume PDF, answers, dossier).
  3. Entries older than the re-apply period are shown as *expired*: their vacancies may appear in results again.
- **Alternative flows:** A1. The user removes an entry → that vacancy may appear again immediately.
- **How a vacancy is matched against the registry:** same source and job id; or, because vacancies get reposted with new ids, the same company and position title.
- **Result:** one place to see where and with what the user has applied; the source of truth for de-duplication across runs and profiles.

## 4. Story map

Backbone (left to right) is the user's journey; each column lists the stories, grouped by delivery slice. Walking skeleton = #22, slices S1–S6 = #26–#31.

| | **Set up** | **Run** | **Review** | **Apply & track** | **Control** |
|---|---|---|---|---|---|
| **Skeleton #22** | Sign in (UC-01) | | | | |
| **S1 #26** | Settings (UC-02); create profile from two files with preview (UC-03); edit, activate, delete (UC-04) | | | | |
| **S2 #27** | | Run now (UC-05); search LinkedIn + Glassdoor, dedupe, hard filter (UC-07 steps 1–3); blocked run handling (UC-08) | Vacancy list of a run with statuses and skip reasons (basic UC-10) | | Browsing limits |
| **S3 #28** | | Employer dossier, re-filter (UC-07 steps 4–5) | Dossier on the vacancy page | | |
| **S4 #29** | | Tailor + review loop (UC-07 steps 6–7) | Tailored resume with highlighted added skills | | |
| **S5 #30** | Re-apply period in Settings (UC-02) | Package preparation, answers, cover note, PDF (UC-07 step 8); summary email (UC-09); dedupe against the applied registry (UC-07 step 2) | Package page (UC-11); reject added skill (UC-12) | Mark applied / skipped (UC-13); applied registry (UC-15) | LLM budget stop (UC-07 A5) |
| **S6 #31** | | Scheduler, run queue (UC-06) | Full run history with counts and cost (UC-10) | | Kill switch (UC-14) |

The **MVP is complete after S6**: every use case in this document is covered.

## 5. Gaps found against the vision and proposed resolutions

| # | Gap | Proposed resolution |
|---|---|---|
| G1 | The vision has no way to start a run by hand, but slices S2–S5 need runs before the scheduler (S6) exists | Add **"Run now"** (UC-05) to the MVP scope |
| G2 | Where application data lives was an open question (vision §13 Q2) | Keep the **two files per profile** from the vision: contacts (phone, email, LinkedIn, current location, languages) come from the **resume**; what a resume lacks (work permit / visa, notice period, relocation, salary range) goes into the **requirements file**. Years per technology are derived from the resume, with overrides in the requirements. Settings hold only the notification email |
| G3 | Where tailoring rules live (vision §13 Q2) | The rules of vision §9 are **system-wide and fixed**; each profile can add free-text **tailoring notes** in the requirements file |
| G4 | Where the company blacklist lives | In the **requirements file** of each profile ("companies to exclude") |
| G5 | The same vacancy can appear on LinkedIn and Glassdoor (seen in spike #2) | Merge into one vacancy within a run; keep both links |
| G6 | The same vacancy can match two profiles | Deduplicate **per profile**: each profile gets its own package (different resume) |
| G7 | What happens to a package when the user rejects an added skill | Regenerate, review again, update the package (UC-12) |
| G8 | Behaviour on login page, CAPTCHA or restriction during a run | Stop, keep partial results, email the user, resume manually (UC-08); restriction also pauses that job board |
| G9 | Review loop could run forever | Max 2 rework rounds, then keep the best version with the reviewer's notes |
| G10 | LLM cap ($10/month) needs a behaviour when reached | Stop the run before the next LLM step, alert the user (UC-07 A5) |
| G11 | Vacancy statuses in the vision cover only packages | Full set: *prepared, applied, skipped, skipped by filter, failed* |
| G13 | A vacancy already applied to must not come back in later runs or other profiles | **Applied registry** (UC-15) filled when the user marks *applied*; de-duplication checks it for every profile; the **re-apply period** in Settings (default 90 days) controls when a vacancy may come back |
| G14 | Added-skill rule had "a couple of days" as the learning limit | Changed to **two weeks** of overview-level learning (vision §9) |
| G12 | The dossier should not be limited to LinkedIn and Glassdoor | Separate **vacancy sources** (LinkedIn, Glassdoor) from **dossier sources** — MVP: LinkedIn, Glassdoor, company website, web search; extensible. Each dossier fact links to its source. Web search costs ~$0.08 per run (within the LLM cap) |

Values left to NFR (#7): default schedule, browsing limits per run, file size limit, retention period.
