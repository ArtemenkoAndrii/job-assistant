# Intent: Worker, A-1 check and email test (skeleton 3/3)

| | |
|---|---|
| **Issue** | #71 (slice 3 of the walking skeleton, epic #22) |
| **Author** | ArtemenkoAndrii (owner); drafted by Claude |
| **Status** | Accepted |
| **Date** | 2026-11-27 |

## Problem

The deployed system has a web app with sign-in (#70) but nothing behind it. The worker is an empty entry point, there is no run queue, and nothing proves the two external links the product depends on: the worker reaching A-1 through `BrowserGateway`, and the system sending email from the dedicated Gmail sender. The A-1 token, the Gmail sender credential, the lease and the "web queues, worker executes" hand-off (ADR-0006, ADR-0007) are all designed but untested end to end. Every later slice (runs, pipeline, summary email) depends on them, so they need to be proven first, in the simplest possible form.

## Proposed outcome

- A "Check A-1" button in the web UI queues a validation run and starts the worker.
- The worker takes the run lease, executes the queued run, opens one allowed page through `BrowserGateway`, and records the snapshot result (success or the reason for failure) on the run.
- The web UI shows the result of the check: a successful snapshot from the deployed system, or a clear failure.
- Only the worker holds the A-1 token; the web service has no access to it.
- A second button, "Send test email", queues a run with `trigger: validation` and a test-email kind. The worker executes it and `Notifier` with the email channel sends one test message from the dedicated sender to the owner's notification email, and it arrives. The web service never sends email: only the worker reads `email-sender` (ADR-0006).
- Both buttons create a `runs` document with `trigger: validation` and `expire_at`, so the real queue and lease are exercised.
- The A-1 check opens a LinkedIn jobs search page that the gateway builds itself (allowed by ADR-0011 §3, no amendment). A successful snapshot also proves A-1 is signed in; a login wall or challenge is recorded as a clear failure reason.
- Tests use a fake MCP server and a fake channel. Nothing in CI reaches A-1 or Gmail.

## Affected users and systems

- Users: the owner, on a phone and on a laptop.
- Systems: `jobfinder-web` (button, queueing, result display, starting the job), `jobfinder-worker` (lease, run execution), `BrowserGateway` (first use, ADR-0011), `Notifier` and `EmailChannel` (ADR-0010), Firestore (`runs`, `locks/worker`), Secret Manager (A-1 token, `email-sender`), service-account permissions and job configuration in `infra/app` and `infra/platform`.
- Use cases: groundwork for UC-05 (Run now), UC-07 (Execute a run) and UC-09 (Receive the run summary); none is delivered in full.

## Constraints

- Accepted ADRs: 0004 (loop in the worker), 0005 (one image, two entry points), 0006 (Cloud Run job, only `worker` reads the A-1 token), 0007 (queue and lease in Firestore, run statuses), 0010 (system sender, Gmail API `gmail.send`, no recipient or token in records and logs), 0011 (gateway allowlists, URL provenance, stop triggers, no JavaScript), 0008/0013 (web auth and Origin check apply to the new button).
- NFR-S1, NFR-S2, NFR-P6 (no token, email or message body in logs), NFR-R2 (one run at a time), NFR-B1 (read only), NFR-C1 (no new paid resources), NFR-M5 (offline tests).
- No LLM calls in this slice (NFR-C2).
- The repo is public: no tokens, addresses or recorded pages with personal data in the diff or fixtures.
- The owner's prerequisites (outside the repo; the slice relies on them and updates the runbook only if a step is missing):
  - the dedicated Gmail account (ADR-0010);
  - an OAuth client in Personal mode, in its own project;
  - the refresh token for `gmail.send`;
  - the `email-sender` secret value (JSON: client id, client secret, refresh token, sender address);
  - the `a1-client-id` and `a1-client-secret` secret values.
- The A-1 hostname must not appear in the repo.
- CI and the dev container never reach A-1 or Gmail; the real check happens after deploy.

## Out of scope

- Profiles, the real run pipeline, scheduling and the hourly tick, kill switch (UC-06, UC-14).
- Search, vacancy pages, dossiers, LLM agents, the summary email content (UC-09 proper).
- The notification email address editing (UC-02), unless the sign-in address from #70 is enough.
- Click policy, board-specific stop triggers and limits beyond what a single page snapshot needs (#24 and later).
- Run history UI (UC-10).
- Follow-up to ADR-0010: a refresh token issued 8 or more days earlier still works (the Personal-mode check); it can only be verified after the first week and is tracked separately.

## Open questions

1. Where does the A-1 endpoint URL live, given the hostname must not be in the repo: a new secret `a1-url` (read only by `worker`), or a GitHub Environment variable passed through Terraform to the job environment? Decide in the spec.

Decided in review: the check opens a LinkedIn jobs search page built by the gateway; the test email has its own button; results are stored as `runs` documents with `trigger: validation` and `expire_at`.
