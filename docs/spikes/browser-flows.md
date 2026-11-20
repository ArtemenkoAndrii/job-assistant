# Spike: browser automation flows

| | |
|---|---|
| **Issue** | #2 |
| **Status** | Pending run |
| **Date** | <yyyy-mm-dd> |
| **Model used** | <model> |
| **How to run** | [spikes/browser-flows/README.md](../../spikes/browser-flows/README.md) |

## Goal

Find out whether an AI agent can reliably search vacancies and walk application flows on LinkedIn and Glassdoor through the Browser MCP endpoint (A-1), and what that costs.

## Summary

<3-5 sentences: does it work, what is the biggest problem, what changes in the plan.>

## 1. Connectivity

| Question | Answer |
|---|---|
| A-1 reachable through Cloudflare Access with service token | |
| Typical latency per MCP call (navigate / snapshot / click) | |
| Session stayed logged in on both sites | |

## 2. Search

| Question | LinkedIn | Glassdoor |
|---|---|---|
| Filters the agent could set (keywords, location, remote, date) | | |
| Vacancies per results page | | |
| Pagination works | | |
| Sign-in walls, blurred or hidden content | | |
| Bot protection or challenges seen | | |

### Field availability (share of vacancies where the field was present)

| Field | LinkedIn | Glassdoor |
|---|---|---|
| Title, company, location | | |
| Work type (remote / hybrid / on-site) | | |
| Salary | | |
| Posted date | | |
| Required skills | | |
| Apply method | | |

## 3. Employer research (Glassdoor)

| Data | Available? | Notes |
|---|---|---|
| What the company does | | |
| Rating and reviews (pros / cons) | | |
| Salary range for a similar role | | |
| Interview questions | | |

## 4. Application flows (dry-run)

| # | Source | Channel (Easy Apply / ATS / custom) | Steps | Screening questions | File upload | Blockers | Stopped at |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

**Resume upload:** Playwright MCP uploads files from the machine where the browser runs (A-1), not from the app. Record what the flows require — this decides how resumes get to A-1.

## 5. Size and cost (input for #3)

| Scenario | MCP calls | Avg snapshot chars | Input tokens | Output tokens | Duration |
|---|---|---|---|---|---|
| 01 LinkedIn search | | | | | |
| 02 LinkedIn details | | | | | |
| 03 Glassdoor | | | | | |
| 04 Apply dry-run | | | | | |

## 6. Reliability and account safety

- Failures and retries:
- Warnings, challenges or restriction notices:
- Anything the agent misread or did unexpectedly:

## 7. Implications

| For | Implication |
|---|---|
| #4 Application channels | |
| #18 Data and file storage (resume upload to A-1) | |
| #20 Browser automation policy (limits, allowed tools) | |
| #19 Agent runtime (token budget, model choice) | |
| #24 Test dataset (what to record, what to anonymize) | |

## 8. Recommendation for MVP

<What goes into MVP as planned, what changes, what is dropped.>
