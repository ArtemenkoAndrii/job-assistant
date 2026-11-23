Scenario: 05-channel-census

Goal: count how often each application channel occurs. Read only — do not click any apply button.

Part A — LinkedIn (25 vacancies):
1. Open https://www.linkedin.com/jobs/search-results/?keywords=<your keywords, e.g. Tech%20Lead%20Java>&f_TPR=r604800
2. Go through the first 25 result cards. Click each card (it opens in place), then read from the details pane:
   - job id (`currentJobId` in the page URL), title, company;
   - apply method: "Easy Apply" or "Apply on company website";
   - for external: the target URL — it is in the `/safety/go/?url=...` link of the apply button; URL-decode it and keep the domain;
   - whether the description contains an email address for applications (yes/no; do not copy the address).
3. Use `browser_find` / targeted snapshots of the details pane, not full-page snapshots.

Part B — Glassdoor (up to 10 vacancies):
4. Open Glassdoor job search with the same keywords and location, past week.
5. For up to 10 cards record: title, company, "Solicitud rápida" / quick apply label (yes/no). Do not click apply.

Classify each external domain:
greenhouse.io → Greenhouse, ashbyhq.com → Ashby, lever.co → Lever, myworkdayjobs.com / workday → Workday,
smartrecruiters.com → SmartRecruiters, teamtailor.com → Teamtailor, personio → Personio, workable.com → Workable,
recruitee.com → Recruitee, bamboohr.com → BambooHR, anything else → "custom: <domain>".

Write to notes/05-channel-census.md:
- a table per vacancy: source, job id, title, company, channel (Easy Apply / ATS name / custom domain / Glassdoor quick apply), email in description (yes/no);
- totals: count and share per channel;
- anything that blocked you.
