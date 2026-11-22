Scenario: 01-linkedin-search

Search LinkedIn Jobs with these criteria (replace with your real ones):
- Keywords: <e.g. "Senior Java Engineer">
- Location / work type: <e.g. Remote, Spain>
- Date posted: past week

Steps:
1. Open https://www.linkedin.com/jobs/ and run the search with the criteria above, using the page's own filters where available.
2. From the first page of results, extract up to 15 vacancies: title, company, location, work type (remote/hybrid/on-site), salary (if shown), posted date, Easy Apply (yes/no).
   Cards have no links: click each card and take the job id from `currentJobId` in the page URL; the vacancy URL is `https://www.linkedin.com/jobs/view/<id>/`.
3. Open page 2 of results once to check how pagination works.

Write to notes/01-linkedin-search.md:
- the extracted vacancies as a table;
- which filters you could set and how;
- which fields were missing and how often;
- how pagination works;
- anything that blocked or slowed you down.
