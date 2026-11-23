Open {url} — a LinkedIn job search with filters already in the URL.
Extract the first 10 vacancies. Cards have no links: click each card and read the job id from `currentJobId` in the page URL.
data: [{"job_id": str, "title": str, "company": str, "location": str, "salary": str|null, "posted": str, "easy_apply": bool}]
