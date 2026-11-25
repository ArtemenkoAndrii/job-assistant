# ADR-0011: Browser automation policy

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #20 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

Job Finder reads LinkedIn, Glassdoor and company websites through **A-1**, a Playwright MCP server on the owner's home server. A-1 is logged in with the owner's accounts (vision A-1, A-2). Its operation is out of scope.

[ADR-0004](0004-agent-runtime.md) put browsing agents in the worker. They call a few Python tools implemented by **`BrowserGateway`**, which holds the only MCP session to A-1 and must enforce this policy in code. The model never sees MCP.

Facts that shape the policy:

**Risk the owner accepts.** Automating the owner's job-board accounts breaks the sites' terms and may get an account restricted (vision §12). The MVP reduces the risk; it does not remove it.

**Spike #2** ([browser flows](../spikes/browser-flows.md)) found:
- LinkedIn needs clicks for filters (open → select → "Show results"), because URL parameters for work type are unreliable.
- Vacancy ids appear only after a card is clicked.
- Element refs go stale after every click.
- Glassdoor showed a Cloudflare challenge on 2 of 3 searches.
- LinkedIn showed an authwall once.
- A job-alert dialog pops up after a Glassdoor search.
- The agent once typed a password, which ended up in recordings.

**Playwright MCP** ([README](https://github.com/microsoft/playwright-mcp)):
- It says plainly that it is **not a security boundary**.
- It enables by default tools that type, fill forms, upload files and run arbitrary page JavaScript; `browser_run_code_unsafe` is described as RCE-equivalent.
- It has guardrail flags: `--allowed-origins`, `--blocked-origins`, `--shared-browser-context`, `--block-service-workers`, timeouts.

**Requirements:**
- NFR-B1 (read only), B2–B6 (limits and pace), B7 (stop conditions).
- NFR-S6 (prompt injection), NFR-S8 (no credentials).
- UC-08 (blocked run), UC-07 A3/A4.

**Delivery.** The MVP never submits applications (#4); there is no "sender".

## Decision drivers

- Read only and polite by construction: rules are code in `BrowserGateway`, not instructions to a model.
- Stop at the first sign of pushback; never retry into a challenge.
- Page content is untrusted. It must not be able to make the system act, or leak personal data.
- Known exit criteria: when the risk is no longer worth it, automation on that board stops.
- Testable offline with recorded pages and a fake MCP (NFR-M5, #24).

## Decision

### 1. Accepted risk and exit criteria

The owner accepts the risk of restriction on the accounts used by A-1. These should be dedicated job-search accounts where possible (spike #2 used a dedicated LinkedIn account).

**Exit criteria**, checked by the worker against counters it already keeps (NFR-O1):

| Signal | Action |
|---|---|
| A restriction or "unusual activity" notice on a board | Stop the run; pause that board's schedule; notify (UC-08 A1). The owner re-enables it by hand |
| A second restriction notice on the same board within 30 days, or any account suspension | Automation on that board is **disabled** until a review (#38). Runs continue with the other boards |
| Challenges (CAPTCHA, "Just a moment…") on more than half of a board's runs over 4 weeks | That board is turned off as a vacancy source; the owner decides on dossier use |
| A credential prompt on a board (login page, authwall) | Stop the run; notify "log in on A-1" (UC-08). It never counts as permission to type |

### 2. Tool allowlist

The browsing agent sees only gateway tools. Each maps to one MCP tool and passes the gateway's checks:

| Gateway tool | MCP tool | Checks |
|---|---|---|
| `navigate(url)` | `browser_navigate` | URL policy (§3); pace; counts a page load |
| `snapshot(target?)` | `browser_snapshot` | Targeted to a region where possible; never `filename`; output size capped |
| `find(text)` | `browser_find` | Read only |
| `click(ref)` | `browser_click` | Click policy (§4); pace; counts a page load if the URL changes |
| `back()` | `browser_navigate_back` | Pace; counts a page load |
| `tabs()` / `close_extra_tabs()` | `browser_tabs` (list, select, close) | At most 2 tabs; no opening a tab with an arbitrary URL |
| `wait(seconds)` | `browser_wait_for` | ≤ 5 s, time only |

**Never called, whatever the model asks** (the gateway has no code path for them):
- typing and form tools: `browser_type`, `browser_fill_form`, `browser_select_option`, `browser_press_key`;
- `browser_file_upload`;
- **all JavaScript**: `browser_evaluate`, `browser_run_code_unsafe`;
- `browser_handle_dialog`;
- `browser_drag`, `browser_drop`, `browser_hover`;
- `browser_take_screenshot`;
- `browser_resize`, `browser_emulate_media`;
- network, console, storage, cookie, devtools and vision tools;
- `browser_close`.

Any tool argument named `filename` is refused (spike #2: paths resolve on A-1).

**JavaScript policy:** pages run their own scripts (the sites need them); Job Finder never injects or evaluates JavaScript.

### 3. Navigation (URL) policy

- Only `https`.
- **Job boards:** the LinkedIn and Glassdoor job, search and company paths. A denylist rejects login, sign-up, account, settings, messaging, notifications, feed, profile-editing, apply and checkout paths.
- **Company websites (dossier):** only a host taken from a link on a job-board page of that company, or from the provider's web search result for that company; its pages within that host; at most 3 pages (NFR-B4).
- Query strings are allowed only for known search parameters on job boards. On other hosts, URLs are passed as found on the page. Agents never build URLs with data of their own.
- Redirects are followed by the browser; the gateway checks the final URL against the same policy and the stop triggers (§6).

### 4. Click policy

Clicks are **denied by default**. Before a click, the gateway looks the ref up in the latest snapshot and allows it only if the element's role and accessible name match a per-site allowlist:
- job cards and their titles;
- pagination ("Next", page numbers);
- the LinkedIn filter controls needed for search (date posted, workplace type, "Show results");
- "Show more" / "… more";
- company-page tabs (About, Jobs, Reviews, Salaries);
- closing known pop-ups (Glassdoor job-alert dialog "Close"/"×");
- the cookie banner's reject or "necessary only" button.

**Always denied**, even if matched: names containing apply, easy apply, submit, send, save, follow, connect, message, sign in, log in, sign up, like, report, share, upload, accept/agree (except cookie "necessary only"). Also any element inside a form other than the filter controls above.

A stale ref (spike #2) is re-found with `find`/`snapshot`; the gateway does not retry blind.

### 5. Limits and pace (NFR-B2–B6)

Enforced by counters in `BrowserGateway` and Firestore (ADR-0007):

| Limit | Value |
|---|---|
| Search result pages per source per run | 2 |
| Vacancies opened per run | 25 |
| Employers researched per run | 8, at most 3 pages each on job boards and 3 on the company site |
| Page loads per board per day, all profiles | 150 (further runs that day skip the board) |
| Pause before every navigate, click and back | random 1–5 s |
| Parallel browsing | none: one MCP session, one run at a time (NFR-R2) |
| Tool calls per task | per ADR-0004 ceilings (search 40, vacancy/employer 20) |

When a limit is reached, the task ends with what it has; it is not an error.

### 6. Stop triggers (NFR-B7)

After every navigate, click and back, the gateway checks the URL, the title and the snapshot text:

| Trigger | Examples | Result |
|---|---|---|
| Login or authwall | `/login`, `/authwall`, `/checkpoint`, sign-in forms | `BrowserBlocked(login)` |
| Challenge | "Just a moment…", "Verify you are human", `challenges.cloudflare.com`, CAPTCHA frames, HTTP 403/429 | `BrowserBlocked(challenge)` |
| Restriction | "unusual activity", "temporarily restricted", account-limited pages | `BrowserBlocked(restriction)` |
| Unknown dialog | a dialog the click policy does not know | `BrowserBlocked(dialog)` |
| A-1 unreachable or errors repeatedly | MCP or Cloudflare Access errors | `BrowserBlocked(a1)` |

`BrowserBlocked` stops browsing at once, with no retries. The run keeps what it already has, gets status *blocked: reason*, and the user is notified (UC-08, ADR-0010). A restriction also pauses the board (§1). The patterns live in one versioned file and are tested against recorded pages (#24).

### 7. Prompt-injection defences (reader / writer separation)

- **Readers have no write tools.** Browsing agents can only read and navigate under §2–§4. Nothing they can call submits, types, uploads or runs JavaScript. A page that says "click Apply" or "type your phone number" cannot be obeyed.
- **No personal data in browsing contexts.** A browsing task receives only search criteria (title keywords, location, work type) or a company or vacancy reference. It never receives the resume, contacts or answers. Even a successful injection has nothing to leak; navigation is also limited to §3, so it cannot carry data to an arbitrary host.
- **Structured outputs only.** Browsing tasks return typed models (Pydantic). URLs are validated against §3; text fields are length-capped. Raw page text is dropped after extraction (ADR-0004) and never reaches the steps that see the resume.
- **Writers have no browser.** Steps that see the resume (tailor, review, answers) have no tools at all. They receive extracted fields marked as untrusted data in the prompt.
- **No sender in the MVP.** Submitting applications (#32) would be a separate agent with its own ADR and human approval per application.

### 8. Account and credential hygiene

- Job-board passwords are never stored, typed or handled by Job Finder (NFR-S8). Login is done by the owner on A-1 (A-2).
- No profile, settings, connections, messages or saved-job changes; the click policy denies them.
- Known side effects are accepted: search keywords go to LinkedIn search history; opened vacancies show as "Viewed" (spike #2).

### 9. Requirements on A-1 (owner's configuration, out of project scope)

Playwright MCP is not a security boundary, and it enables `browser_run_code_unsafe` by default. Whoever holds the A-1 service token can therefore run code in the A-1 browser. Hence:
- The A-1 token is held only by `worker` (ADR-0006) and rotated every 90 days (NFR-S5).
- A-1 runs with:
  - `--shared-browser-context` (one context for our single session; the spike #3 blank pages);
  - a persistent `--user-data-dir` for the logged-in profile;
  - `--block-service-workers`;
  - the browser sandbox on;
  - an output directory without anything else in it.
- The A-1 container has no host mounts beyond its profile and no access to the home network beyond the internet.
- If Playwright MCP adds a way to disable tools, A-1 disables everything outside §2. Until then, an allowlisting proxy in front of A-1 is a recommended follow-up for the owner.

### 10. Validation on A-1 (before #27 uses browsing)

The owner runs a short checklist with the spike kit and records results in `docs/spikes/`:
1. With `--shared-browser-context`, a navigate followed by a snapshot from one long MCP session never sees a blank page (20 calls).
2. The LinkedIn search with the past-week and remote filters works using only clicks allowed by §4.
3. A Glassdoor company page and its job-alert dialog close work under §4.
4. A login page or challenge is detected by the §6 patterns on a recorded page.

If item 1 or 2 fails, this ADR is revisited before #27.

Out of scope: submitting applications (#32); operating A-1; the post-MVP review of the approach (#38).

## Consequences

- Positive: read-only behaviour and politeness are guaranteed by code paths, not by model obedience; injected instructions have no tools to act with and no personal data to leak.
- Positive: clear stop behaviour and exit criteria protect the owner's accounts and make the risk visible.
- Negative: allowlists of clicks, paths and stop patterns are site-specific and will break when sites change; a mismatch stops a run (safe), and the patterns need maintenance with recorded-page tests.
- Negative: the strict click policy may miss legitimate controls; each addition is a reviewed change to the allowlist.
- Negative: A-1 itself still exposes powerful tools; the protection depends on keeping its token secret, until the owner adds a tool-filtering proxy.
- Follow-ups:
  - **#22:** `BrowserGateway` skeleton with the tool allowlist and one navigate + snapshot.
  - **#24:** recorded pages for stop triggers and the click policy.
  - **#27:** the search flow under this policy.
  - **#38:** review against real runs.
  - **The owner:** A-1 flags and the validation checklist (§9–§10).
  - **On acceptance:** CLAUDE.md index; architecture Q7.
