# Spec: Worker, A-1 check and email test (skeleton 3/3)

| | |
|---|---|
| **Issue** | #71 |
| **Intent** | [intent.md](intent.md) |
| **Status** | Accepted |
| **Date** | 2026-11-27 |

## Related ADRs

- ADR-0004 Agent runtime: the loop runs in the worker. This slice has no agent and no LLM call; it only gives the worker its first run loop.
- ADR-0005 Application stack: one image, two entry points. The worker is `python -m jobfinder.worker`; the web app adds two routes and one htmx fragment.
- ADR-0006 Hosting: the web app queues a run and starts a job execution through the Cloud Run Admin API (the web service account already has `run.invoker` on the job). Only `worker` reads the A-1 and `email-sender` secrets (`secrets.tf`).
- ADR-0007 Data and storage: `runs` documents with `status` and `expire_at`, and the lease document `locks/worker`. The queue and lease rules in ADR-0007 are implemented as written.
- ADR-0008 / ADR-0013 Authentication and Origin check: both new routes sit on the protected router.
- ADR-0010 Notifications: `Notifier` calls channels; `EmailChannel` sends through the Gmail API with the `email-sender` credential; the recipient is the owner's notification email; records and logs never contain the recipient, token or body.
- ADR-0011 Browser policy: `BrowserGateway` is the only path to A-1. The check uses the allowed tools `navigate` and `snapshot` only, with a URL the gateway builds itself (§3), the stop triggers (§6) and the owner-identifier redaction.

No contradiction with an accepted ADR. One extension (a new secret `a1-url`, read at execution time rather than injected) is under *Flagged concerns*.

## Requirements

### Functional

| ID | Requirement | Use case |
|---|---|---|
| R1 | The Settings page has a "System checks" card with two buttons, "Check A-1" and "Send test email". | UC-05 (groundwork) |
| R2 | A button press creates a `runs` document with `trigger: validation`, `kind` (`a1_check` or `email_test`), status `queued` and `expire_at`, then starts a job execution of `jobfinder-worker`. A press while a run of the same kind is `queued` or `running` creates no second run. | UC-05 |
| R3 | The worker takes the lease (`locks/worker`) in a transaction, marks runs left `running` by a crashed execution as `failed`, executes the oldest queued run, and releases the lease. An execution that finds a valid lease exits without touching any run. The lease is renewed every 2 minutes; losing it stops the run (*stopped: lease lost*). | UC-07 (groundwork) |
| R4 | `a1_check`: through `BrowserGateway` the worker navigates to a LinkedIn jobs search URL that the gateway builds itself from a fixed, non-personal keyword, takes one snapshot, and records the result on the run. | UC-07 (groundwork) |
| R5 | The gateway evaluates stop triggers after the navigate and the snapshot. A login wall, authwall, challenge or restriction ends the check as `failed` with a specific reason; there is no retry. | UC-08 (groundwork) |
| R6 | `email_test`: the worker reads the notification email from `settings/owner` and calls `Notifier.notify(TestMessage)`; the email channel sends one message from the dedicated sender and the run records whether it was sent. | UC-09 (groundwork) |
| R7 | The card shows the latest run of each kind: never run, queued, running, succeeded, or failed with a plain-English reason, and updates itself while a run is queued or running. | UC-10 (groundwork) |
| R8 | The web service never reads the A-1 or email secrets and never sends email; the worker alone holds them. | NFR-S2 |
| R9 | The secret `a1-url` exists in the platform layer with `worker` as its only reader, and the runbook and architecture document the step to add its value. | NFR-S2 |

### Non-functional

- NFR-S1: both new routes require the owner (Origin check, then IAP token and owner check).
- NFR-S2: A-1 URL, A-1 client id and secret, and `email-sender` are read from Secret Manager by the worker at execution time, through the Secret Manager API; they are never environment variables or secret references on either Cloud Run resource.
- NFR-S6, NFR-B1: page content is data; the check has no LLM and no tool outside `navigate` and `snapshot`.
- NFR-B5, NFR-B6: the navigate counts as one LinkedIn page load in the daily counter; a random 1–5 s pause sits between the two browser actions.
- NFR-B7: stop triggers as above.
- NFR-R2: one run at a time (lease).
- NFR-P6: no token, email address, A-1 host, page text or message body in logs or records.
- NFR-M5: tests use a fake MCP session and a fake channel; CI never reaches A-1, LinkedIn or Gmail.
- NFR-U1, NFR-U4: the card works at 360 px and on desktop and is accessible.
- NFR-C1, NFR-C2: no new paid resource, no LLM call.

## Acceptance criteria

- **AC1** — Given the owner is signed in, when they open Settings, then a "System checks" card shows two buttons and each check's last result, or "Not run yet".
- **AC2** — Given no run of kind `a1_check` is queued or running, when the owner presses "Check A-1", then one `runs` document exists with `trigger: validation`, `kind: a1_check`, status `queued` and an `expire_at`, and the job starter was called once.
- **AC3** — Given an `a1_check` run is `queued` or `running`, when the owner presses "Check A-1" again, then no second run is created and the card shows the existing run.
- **AC4** — Given the job starter fails, when the owner presses a button, then the run stays `queued`, the card says the worker could not be started and that it will retry at the next scheduled start, and the page does not error.
- **AC5** — Given a request without a valid IAP token or from the wrong account, or with a missing or cross-origin `Origin`, when it posts to either new route, then it is refused and no run is created.
- **AC6** — Given the lease is free and one queued run exists, when the worker starts, then it takes the lease, sets the run `running`, executes it, sets a final status, and releases the lease.
- **AC7** — Given the lease is held and not expired, when a second worker starts, then it exits with code 0 and changes no run.
- **AC8** — Given a run left `running` by a crashed execution and an expired lease, when a worker starts, then that run becomes `failed` (reason `worker_crashed`) before the next queued run is executed.
- **AC9** — Given a fake MCP session that returns a normal results snapshot, when the worker executes an `a1_check` run, then the run ends `completed` with `result.ok: true`, the snapshot size and the page-load counter incremented by one.
- **AC10** — Given the fake session records its calls, when the check runs, then the only calls are one `browser_navigate` to an `https` LinkedIn jobs search URL built by the gateway and one `browser_snapshot` without a `filename` argument, with the pause between them taken from the injected sleep function.
- **AC11** — Given recorded-style fake pages for a login wall, an authwall, a challenge ("Just a moment…", HTTP 403) and an A-1 error, when the check runs, then the run ends `failed` with the reasons `login_wall`, `login_wall`, `challenge` and `a1_unreachable` respectively, and the session is not asked for further pages.
- **AC12** — Given Cloudflare Access rejects the service token, when the check runs, then the run ends `failed` with reason `a1_auth`.
- **AC13** — Given the daily LinkedIn page-load counter is at its limit, when the check runs, then no browser call is made and the run ends `failed` with reason `daily_limit`.
- **AC14** — Given a fake channel and `settings/owner` with a notification email, when the worker executes an `email_test` run, then the channel receives one `TestMessage` addressed to that email, and the run ends `completed` with `result.sent: true`.
- **AC15** — Given the Gmail API returns an error (including `invalid_grant`) or `email-sender` is missing, when the worker executes an `email_test` run, then the run ends `failed` with reason `email_auth`, `email_send_failed` or `email_not_configured`, and the other channels are unaffected.
- **AC16** — Given a run of either kind with a fake token, recipient and snapshot text, when it completes or fails, then none of those values appear in captured logs or in the stored run document.
- **AC17** — Given a viewport of 360 px, when the card renders in each state (never run, queued, running, succeeded, failed, start failed), then there is no horizontal scrolling, each button is at least 44 px high, and the state is shown as text, not by colour alone.
- **AC18** — Given the Terraform sources, when the lint test reads them, then `a1-url`, `a1-client-id`, `a1-client-secret` and `email-sender` have `worker` as the only reader, and neither the web service nor the worker job has an environment variable or secret reference for any of them.
- **AC19** — Given the deployed system, when the owner presses "Check A-1" on the real service, then the card shows a successful snapshot, and when they press "Send test email", a message from the dedicated sender arrives (manual proof after deploy, recorded in `plan.md`).
- **AC20** — Given CI, when the full test suite runs, then a `conftest.py` autouse fixture that patches `socket.socket.connect` makes any connection to an address other than `localhost`, `127.0.0.1` or `::1` raise an error, and a test proves the fixture blocks an outside address (fake MCP, fake channel and fake secret reader only).
- **AC21** — Given the secret reader finds no secret or no version for `a1-url`, `a1-client-id` or `a1-client-secret`, when the worker executes an `a1_check` run, then the run ends `failed` with reason `a1_not_configured` and the gateway is never created; given a missing `email-sender`, the `email_test` run ends `failed` with `email_not_configured`.
- **AC22** — Given the app, when the Settings page is rendered, then it loads htmx from `/static/htmx.min.js` (a pinned copy in the repo) and from no external host, and a request to that path without a valid IAP token is refused like `/static/app.css`.

## Design

### Flow

```
Owner ──POST /checks/{a1|email}──► web: create run (queued) ──► Admin API: run job "jobfinder-worker"
                                                                      │
                          Firestore: runs, locks/worker  ◄────────────┘ worker: lease → oldest queued run
                                                                      │
                          kind a1_check  → BrowserGateway → A-1 (Cloudflare Access) → LinkedIn page
                          kind email_test → Notifier → EmailChannel → Gmail API → owner's inbox
                                                                      │
Owner ◄── GET /checks (htmx fragment, polls while queued/running) ◄── run result
```

### Data

`runs/{id}` (ADR-0007 fields plus):

| Field | Value |
|---|---|
| `trigger` | `validation` |
| `kind` | `a1_check` or `email_test` |
| `status` | `queued`, `running`, `completed`, `failed`, `stopped` |
| `created_at`, `started_at`, `finished_at`, `expire_at` | timestamps; `expire_at` is 30 days after creation (a validation record is operational, shorter than the 12-month cap in ADR-0007) |
| `result` | `{ok: bool, reason: <code>}`; plus `snapshot_chars` for `a1_check`, `sent: bool` for `email_test` |

`profile` is empty. The record stores no URL, host, page text, address or message body. A run record that was `queued` but could not be started carries `start_error: true` so the card can say so.

`locks/worker`: `{holder, expires_at}` as in ADR-0007.

`page_loads/linkedin-<yyyymmdd>`: `{count, expire_at}` — the existing collection from ADR-0007 (with its TTL policy), used as the daily page-load counter (NFR-B5, limit 150); incremented in a transaction, only by the gateway. No new collection and no new TTL policy.

### Components (under `apps/jobfinder/src/jobfinder`)

- `domain/runs.py`: `Run`, `RunKind`, `RunStatus`, reason codes (an enum, so UI text is a fixed lookup).
- `storage/runs_repo.py`: `RunRepository` protocol with in-memory and Firestore implementations: `create_if_none_active(kind)`, `latest(kind)`, `oldest_queued()`, `mark(...)`, `fail_stale_running()`. `storage/lease.py`: `Lease` protocol, transactional take, renew, release, in-memory and Firestore implementations. `storage/page_loads.py`: the page-load counter over `page_loads`. `storage/secret_reader.py`: `SecretReader` protocol, a Secret Manager implementation (below) and an in-memory fake.
- `web/jobs.py`: `JobStarter` protocol; `CloudRunJobStarter` calls `POST https://run.googleapis.com/v2/projects/<number>/locations/<region>/jobs/jobfinder-worker:run` with the service's own ADC token over `httpx`; a fake in tests. `web/checks.py`: the routes `POST /checks/a1`, `POST /checks/email` and `GET /checks`, all on the protected router, returning the card fragment.
- `worker/main.py`: `run_once()`: lease, housekeeping, oldest queued run, dispatch by `kind`, release; renewal as a background task; exit code 0 unless the process itself fails.
- `browser/gateway.py`: `BrowserGateway(session, counter, sleep, rng)` with `navigate_search()` and `snapshot()`; builds the LinkedIn URL from a constant keyword; checks `https` and host; runs `stop_triggers.evaluate(url, title, text, status)` after each result; raises `BrowserBlocked(reason)`. `browser/mcp_session.py`: `McpSession` protocol and the real client (streamable HTTP, headers `CF-Access-Client-Id` and `CF-Access-Client-Secret`); the gateway never imports it directly, so tests pass a fake session.
- `notify/`: `Notifier`, `Event`/`TestMessage`, `Channel` protocol, `EmailChannel` (token exchange at `oauth2.googleapis.com`, send at `gmail.googleapis.com` over `httpx`; plain-text MIME built in memory). The notifier calls each enabled channel independently.

### Page-load and pace rules used by the check

One LinkedIn page load (counter +1), one snapshot, a random 1–5 s pause between them (injectable sleep and RNG), no click, no typing, no second page. The snapshot text is inspected for stop triggers and its length is recorded, then discarded; it is never stored, logged or sent anywhere.

### Configuration and infrastructure

- **No secret references in Cloud Run.** `a1-url`, `a1-client-id`, `a1-client-secret` and `email-sender` are not environment variables or secret refs on the worker job or the web service: three of them have no version today and Cloud Run rejects a job update that references a secret without a version, so the deploy would break until every owner prerequisite is done. Instead the worker reads them at execution time with `SecretReader`, which calls the Secret Manager API method `versions.access` for the `latest` version of the named secret, over `httpx` with its own ADC token (the worker already has `secretAccessor`). It reads a secret only when the run kind needs it, so a missing value fails only that check. A missing secret, a secret without a version or a disabled version (404 or `FAILED_PRECONDITION`) is *not configured*: `a1_not_configured` or `email_not_configured`. Any other error is `a1_unreachable` / `email_send_failed`. Values are held in memory for the run and never logged. The only environment added to the worker job is `JOBFINDER_ENVIRONMENT=production` and `JOBFINDER_PROJECT_NUMBER`.
- **A-1 endpoint URL: a new secret `a1-url`, read only by `worker`** (decided in the intent review). A GitHub Environment variable would pass through Terraform and show up in the `app` plan and drift logs, which are public; a secret keeps the hostname out of the repo, the state and every log.
- **Platform-layer change (owner applies before the app deploy):** in `infra/platform/secrets.tf`, add `"a1-url" = ["worker"]` to the secret map, which creates the container and grants `secretAccessor` to the worker service account only, as for `a1-client-id` and `a1-client-secret`. The owner then adds the secret value. Only this `secrets.tf` change must precede the deploy; the value and the other prerequisites can follow, because the app layer references no secret. Until the value is added, the check reports `a1_not_configured`.
- **Runbook:** `docs/runbooks/bootstrap.md` gets the new step (apply the platform layer, add the `a1-url` value next to the other A-1 values), and `docs/architecture.md` §Secret Manager lists `a1-url`. Both are part of this change.
- Web service: no new variable or secret. It starts the job by the constant name `jobfinder-worker` using its existing `JOBFINDER_PROJECT_NUMBER`, `region` and its existing `run.invoker` on the job.
- Settings: `config.py` gains no secret fields. The worker's settings are the project number and the environment; secret values come only from `SecretReader`.
- **htmx:** a pinned release of htmx is vendored as `web/static/htmx.min.js` (version in the file header; no CDN, no external script host), included by `base.html` and served through a protected route like `app.css`: `@protected.get("/static/htmx.min.js")`.
- Dependency: the official `mcp` Python SDK for the streamable-HTTP client. If it does not support Python 3.14 or fails `pip-audit` (NFR-S7), the fallback is a minimal JSON-RPC client over `httpx` behind the same `McpSession` protocol.

### Reason codes shown to the owner

| Code | Text on the card |
|---|---|
| `a1_not_configured` | A-1 is not configured. |
| `a1_unreachable` | A-1 did not answer. Is the home server running? |
| `a1_auth` | A-1 refused the service token. |
| `login_wall` | LinkedIn asked for a sign-in. Sign in to A-1's browser again. |
| `challenge` | LinkedIn showed a human check. Try again later. |
| `empty_snapshot` | The page came back empty. |
| `daily_limit` | The daily page-load limit is reached. |
| `email_not_configured` | The email sender is not configured. |
| `email_auth` | Gmail refused the sender's credential. It needs a new consent. |
| `email_send_failed` | Gmail could not send the message. |
| `no_notification_email` | No notification email is saved yet. |
| `worker_crashed` | The worker stopped during the check. |
| `lease_lost` | The worker lost its lock and stopped. |

## Security, privacy and cost

- **Security:**
  - Both routes are on the protected router: Origin check, then IAP token and owner check (NFR-S1; AC5).
  - The A-1 URL, client id and secret, and the email sender credential are read only by the worker, at execution time, through the Secret Manager API; neither Cloud Run resource has them as environment variables, and the web service cannot read them (NFR-S2, ADR-0006; AC18, AC21).
  - Whoever holds the A-1 token can run code in A-1's browser (ADR-0011); the worker is the only holder, and the check calls only `navigate` and `snapshot`.
  - No LLM and no agent: page content is compared with fixed stop patterns, not interpreted (NFR-S6). No form is filled or submitted (NFR-B1). Stop conditions follow ADR-0011 §6 (NFR-B7; AC11).
  - The navigation URL is built by the gateway from constants; no user or page input reaches it.
  - Tests and CI use a fake session and a fake channel (NFR-M5; AC20).
  - Outbound hosts at runtime: the A-1 host (Cloudflare Access), `oauth2.googleapis.com`, `gmail.googleapis.com`, `secretmanager.googleapis.com` (worker), `run.googleapis.com` (web). htmx is served from the app itself, so no browser request goes to a third-party host. Cloud Run egress is open; the dev container needs none.
  - New dependency: `mcp` (see above), checked by `scripts/audit.sh` (NFR-S7).
- **Privacy:**
  - Stored: `runs` documents with kind, status, timestamps, a reason code, a character count and a sent flag; a daily counter. No address, URL, host, page text or message body is stored or logged (NFR-P1, NFR-P6; AC16). Errors are logged by exception class and code only, since a library message can contain a URL.
  - The test email is sent to the owner's own notification email from `settings/owner`; the dedicated sender's Sent folder keeps a copy (accepted in ADR-0010 §6). The body contains no personal data.
  - Retention: run records expire after 30 days (within NFR-P3's cap); the page-load counter is the existing `page_loads` document with its TTL (ADR-0007).
  - Page snapshots may show the owner's name in the LinkedIn header (spike #2); the snapshot is discarded in memory and never stored.
- **Cost:** +$0 per run in LLM cost (no LLM call); cloud: free tier. A worker execution lasts under a minute at 1 vCPU, a handful of Firestore reads and writes, one Gmail API call (free). Browsing: one LinkedIn page load per "Check A-1" press, against the daily limit of 150 (NFR-B5). No new paid resource (NFR-C1).

## UX

A "System checks" card on the Settings page (the page is currently an empty placeholder), English text, no internal IDs.

- **360 px phone:** the card is one column. Each check is a block: a heading ("A-1 browser", "Email"), a one-line description, a full-width button of at least 44 px, and a status line below. No table.
- **Desktop (1280 px):** the two blocks sit side by side in a two-column grid inside the existing page shell.
- **States per check:** never run ("Not run yet"), queued ("Waiting for the worker…"), running ("Running…"), succeeded ("Passed" with the time and, for A-1, "Snapshot received, N characters"; for email, "Message sent. Check your inbox."), failed (reason text from the table above and the time), start failed ("The worker could not be started. It will retry at the next scheduled start."). While queued or running the button is disabled and the block polls `GET /checks` every 3 s with htmx; the status region has `aria-live="polite"`.
- **One tap:** the button is the only action; the result needs no navigation.
- **Accessibility:** buttons have visible text labels, status is text plus a symbol, never colour alone, contrast WCAG 2.2 AA, keyboard reachable (NFR-U4).
- **Email:** subject "Job Finder test message", a two-line plain-text body that says the sender works; readable on a phone mail client; no link and no personal data.

## Flagged concerns

1. **New secret `a1-url`: the platform change precedes the deploy.** The architecture's Secret Manager line lists "A-1 id and secret" but not the endpoint URL. Adding `a1-url` extends it and does not contradict ADR-0006. You apply the platform change (container and worker accessor) before CI deploys; the value and the other prerequisites can follow in any order, because no Cloud Run resource references a secret and a missing one only makes the check report `a1_not_configured` or `email_not_configured`.
2. **Owner prerequisites before the proof.** The dedicated Gmail account, the OAuth client in Personal mode in its own project, the `gmail.send` refresh token, the `email-sender` JSON value, and the `a1-client-id`, `a1-client-secret` and `a1-url` values. Without them the checks fail with the reasons above, which is correct behaviour but no proof for AC19.
3. **Retention of validation records** is 30 days, shorter than the 12 months in ADR-0007's table. That table sets a maximum, so I read it as compatible; flagging it so you can ask for 12 months instead.
4. **Each press loads one LinkedIn search page in the owner's logged-in session** (it appears in search history). Within NFR-B5; the duplicate guard stops repeated presses while a run is active, but there is no cooldown after it finishes.
5. **`mcp` dependency on Python 3.14.** If the SDK does not install or fails the audit, the plan switches to the `httpx` fallback client without changing the design.
6. **Firestore transaction logic** (lease, `create_if_none_active`) has in-memory fakes in CI but no emulator test; its first real exercise is AC19. Adding the Firestore emulator to CI would need a new dev-container component, so it is not proposed here.

## Out of scope

- Profiles, scheduling logic (the existing hourly Scheduler starts the job; this worker only runs queued validation runs), the kill switch, "Run now" for profiles (UC-05 proper), run history UI (UC-10).
- Any LLM call, agent task, click, search filter, vacancy page or company page; Glassdoor.
- The summary email (UC-09 content); editing the notification email (UC-02).
- Glassdoor and LinkedIn stop-trigger pattern coverage beyond what the check needs (recorded-page tests are #24).
- ADR-0010 follow-up: verifying that a refresh token issued 8 or more days earlier still works (Personal mode). It can only be checked after the first week and is tracked separately.
- An allowlisting proxy in front of A-1 (ADR-0011 follow-up for the owner).
