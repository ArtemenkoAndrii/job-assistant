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
| **LLM provider** | External system | OpenAI models for agents |
| **Email service** | External system | Delivers summary and alert emails |

## 2. Use case overview

| ID | Use case | Primary actor | Slice |
|---|---|---|---|
| UC-01 | Sign in | User | Skeleton #22 |
| UC-02 | Manage personal settings | User | S1 #26 |
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

## 3. Use cases

### UC-01 Sign in

- **Actor:** User. **Trigger:** opens the web app.
- **Main flow:**
  1. The user signs in with the chosen method (ADR #17).
  2. On first sign-in the system creates the user record and takes the sign-in email as the notification email.
  3. The user lands on the profiles page.
- **Alternative flows:**
  - A1. Sign-in fails or is cancelled → the user stays on the sign-in page with a message.
  - A2. The account is not the allowed owner account (MVP is single-user) → access denied.
- **Result:** an authenticated session on desktop or mobile.

### UC-02 Manage personal settings

- **Actor:** User. **Precondition:** signed in.
- **Main flow:**
  1. The user opens Settings.
  2. Edits the notification email and the **application data** that does not depend on the profile: phone number, current location, relocation willingness, work permit and visa sponsorship status, notice period, languages, LinkedIn profile URL.
  3. Edits the **company blacklist** (companies always skipped, e.g. the current employer).
  4. Saves.
- **Alternative flows:**
  - A1. Invalid email or phone → field error, nothing saved.
  - A2. Application data missing → runs still work; packages show "fill in Settings" where an answer needs it.
- **Result:** settings used by every profile.

### UC-03 Create a search profile

- **Actor:** User. **Precondition:** signed in, fewer than 3 profiles.
- **Main flow:**
  1. The user clicks "New profile" and gives it a name.
  2. Uploads a resume (.pdf, .txt, .md).
  3. Uploads a requirements file (.pdf, .txt, .md): role, stack, seniority, salary expectation, location and work type, optional tailoring notes (e.g. "emphasize Kotlin").
  4. Optionally sets years of experience per key technology (used for form answers).
  5. The system extracts the text of both files and shows a short preview (role, stack, salary, location) so the user can see it was read correctly.
  6. The user saves; the profile is created **inactive**.
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
  2. **Deduplicate**: drop vacancies already processed for this profile; merge the same vacancy found on both sources.
  3. **Hard-filter**: salary, location, work type, stack, blacklist. Rejected vacancies are kept with the reason (*skipped by filter*).
  4. **Research** each remaining employer (dossier from LinkedIn and Glassdoor; one dossier per company per run).
  5. **Re-filter** with the dossier.
  6. **Tailor** the resume for each remaining vacancy.
  7. **Review** each tailored resume; on "rework" tailor again (max 2 rounds), then keep the best version with the reviewer's issues attached.
  8. **Prepare the package**: resume PDF, dossier, answers from settings and profile, cover note, link and channel. Status *prepared*.
  9. Record run statistics and cost; send the summary (UC-09).
- **Alternative flows:**
  - A1. Nothing found or everything filtered out → the run completes with zero packages; the summary says so.
  - A2. A single vacancy or employer page fails (page did not load, unknown layout) → that vacancy is marked *failed* with the reason; the run continues.
  - A3. Session expired, CAPTCHA, Cloudflare challenge or restriction notice → **blocked run**, UC-08.
  - A4. Glassdoor blocked but LinkedIn works → continue without Glassdoor data; the dossier marks what is missing.
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
  - A1. An answer needs data missing in Settings → shown as "fill in Settings"; after filling, answers are regenerated without re-tailoring.
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
- **Main flow:** after applying, the user marks the vacancy *applied* (date recorded); or marks it *skipped* with an optional reason.
- **Result:** run history counts applications; skip reasons help tune filters later.

### UC-14 Stop all runs (kill switch)

- **Actor:** User.
- **Main flow:** the user turns on the kill switch → the running run stops after the current step, queued runs are dropped, no new runs start.
- **Alternative flows:** A1. Turning the kill switch off → scheduled runs resume from the next slot.
- **Result:** the system stops touching the job boards immediately.

## 4. Story map

Backbone (left to right) is the user's journey; each column lists the stories, grouped by delivery slice. Walking skeleton = #22, slices S1–S6 = #26–#31.

| | **Set up** | **Run** | **Review** | **Apply & track** | **Control** |
|---|---|---|---|---|---|
| **Skeleton #22** | Sign in (UC-01) | | | | |
| **S1 #26** | Personal settings, blacklist (UC-02); create profile with preview (UC-03); edit, activate, delete (UC-04) | | | | |
| **S2 #27** | | Run now (UC-05); search LinkedIn + Glassdoor, dedupe, hard filter (UC-07 steps 1–3); blocked run handling (UC-08) | Vacancy list of a run with statuses and skip reasons (basic UC-10) | | Browsing limits |
| **S3 #28** | | Employer dossier, re-filter (UC-07 steps 4–5) | Dossier on the vacancy page | | |
| **S4 #29** | | Tailor + review loop (UC-07 steps 6–7) | Tailored resume with highlighted added skills | | |
| **S5 #30** | | Package preparation, answers, cover note, PDF (UC-07 step 8); summary email (UC-09) | Package page (UC-11); reject added skill (UC-12) | Mark applied / skipped (UC-13) | LLM budget stop (UC-07 A5) |
| **S6 #31** | | Scheduler, run queue (UC-06) | Full run history with counts and cost (UC-10) | | Kill switch (UC-14) |

The **MVP is complete after S6**: every use case in this document is covered.

## 5. Gaps found against the vision and proposed resolutions

| # | Gap | Proposed resolution |
|---|---|---|
| G1 | The vision has no way to start a run by hand, but slices S2–S5 need runs before the scheduler (S6) exists | Add **"Run now"** (UC-05) to the MVP scope |
| G2 | Where application data lives was an open question (vision §13 Q2) | **Personal data** (phone, location, work permit, notice period, languages, LinkedIn URL) in **Settings**, shared by all profiles; **profile-specific data** (salary expectation, location and work type preferences, years per technology) in the **profile** / requirements file |
| G3 | Where tailoring rules live (vision §13 Q2) | The rules of vision §9 are **system-wide and fixed**; each profile can add free-text **tailoring notes** in the requirements file |
| G4 | Blacklist scope unclear | **User-level** (Settings), applies to all profiles |
| G5 | The same vacancy can appear on LinkedIn and Glassdoor (seen in spike #2) | Merge into one vacancy within a run; keep both links |
| G6 | The same vacancy can match two profiles | Deduplicate **per profile**: each profile gets its own package (different resume) |
| G7 | What happens to a package when the user rejects an added skill | Regenerate, review again, update the package (UC-12) |
| G8 | Behaviour on login page, CAPTCHA or restriction during a run | Stop, keep partial results, email the user, resume manually (UC-08); restriction also pauses that job board |
| G9 | Review loop could run forever | Max 2 rework rounds, then keep the best version with the reviewer's notes |
| G10 | LLM cap ($10/month) needs a behaviour when reached | Stop the run before the next LLM step, alert the user (UC-07 A5) |
| G11 | Vacancy statuses in the vision cover only packages | Full set: *prepared, applied, skipped, skipped by filter, failed* |

Values left to NFR (#7): default schedule, browsing limits per run, file size limit, retention period.
