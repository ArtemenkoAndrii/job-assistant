# Plan: Worker, A-1 check and email test (skeleton 3/3)

| | |
|---|---|
| **Issue** | #71 |
| **Spec** | [spec.md](spec.md) (Accepted) |
| **Status** | Approved |
| **Date** | 2026-11-27 |

## Context

Slice 3 of the walking skeleton (#22). The web app is deployed behind IAP with empty pages (#70); the worker job only prints a line. This slice adds the run queue and lease, a "System checks" card on Settings with two buttons, the first use of `BrowserGateway` (one LinkedIn search page through A-1) and the first use of `Notifier` with the Gmail channel (one test message). Spec R1–R9, AC1–AC22.

Reused as they are: `create_app`, `protected` router, `_page`, the `/static/app.css` route pattern in `src/jobfinder/web/app.py`; `check_origin`, `require_owner` (`web/csrf.py`, `web/auth.py`); `SettingsRepository` pattern (protocol + in-memory + lazy Firestore) in `storage/settings_repo.py`; `httpx` (already a runtime dependency); `datastore.user` for `web` and `worker`, `run.invoker` for `web` on the job, `secretAccessor` for `worker`, TTL on `expire_at` for `runs` and `page_loads` (`infra/platform/firestore.tf`), the hourly scheduler (`infra/app/scheduler.tf`) that doubles as the retry for a queued run.

Right after approval, the first commit saves this plan as `docs/changes/71-worker-a1-check-email/plan.md`; code comes after. Branch `71-worker-a1-check-email` already holds the intent and spec.

## Files that change

| File | Change |
|---|---|
| `docs/changes/71-worker-a1-check-email/plan.md` | new, this plan (first commit) |
| `infra/platform/secrets.tf` | add `"a1-url" = ["worker"]` (container + worker accessor); owner applies after the merge |
| `infra/platform/iam.tf` | add `roles/datastore.indexViewer` to the `app-plan` roles and rewrite the comment above it (ADR-0009 lists it; it was skipped only because the app layer had no index); owner applies after the merge, otherwise `app-plan` and drift fail with permission denied on the new indexes |
| `infra/app/cloud_run_worker.tf` | env `JOBFINDER_ENVIRONMENT=production`, `JOBFINDER_PROJECT_NUMBER`; no secret refs |
| `infra/app/indexes.tf` | composite indexes: `runs (status, created_at)` for the oldest queued run, `runs (kind, created_at desc)` for the latest per kind |
| `docs/runbooks/bootstrap.md` | step 5: six secrets, `a1-url` row (value: A-1 endpoint URL, needed from #71); order note: merge → apply `infra/platform` → add values |
| `docs/architecture.md` | Secret Manager line lists `a1-url`; worker reads secrets at execution time |
| `apps/jobfinder/pyproject.toml`, `uv.lock` | `uv add mcp` (fallback in Risks) |
| `src/jobfinder/domain/runs.py` | new: `RunKind`, `RunStatus`, `Reason` enum, `Run` dataclass, reason → card text lookup |
| `src/jobfinder/storage/runs_repo.py` | new: `RunRepository` protocol; in-memory and Firestore implementations (`create_if_none_active`, `latest`, `oldest_queued`, `mark_running/finished`, `fail_stale_running`, `set_start_error`) |
| `src/jobfinder/storage/lease.py` | new: `Lease` protocol; transactional take/renew/release on `locks/worker`; in-memory and Firestore |
| `src/jobfinder/storage/page_loads.py` | new: daily counter over `page_loads/linkedin-<yyyymmdd>` (`count`, `expire_at`), transactional increment, limit 150 |
| `src/jobfinder/storage/secret_reader.py` | new: `SecretReader` protocol; Secret Manager implementation (`versions.access`, `latest`, ADC token via `google.auth`, `httpx`); in-memory fake; 404 / `FAILED_PRECONDITION` → `NotConfigured` |
| `src/jobfinder/browser/{gateway,stop_triggers,mcp_session}.py` | new: `BrowserGateway` (navigate to the gateway-built search URL, one snapshot, pause, counter, stop triggers, `BrowserBlocked(reason)`); pure `evaluate()` for stop patterns (English and Spanish login, authwall, challenge, 403/429); `McpSession` protocol and the streamable-HTTP client with the Cloudflare Access headers |
| `src/jobfinder/notify/{notifier,email_channel}.py`, `notify/__init__.py` | new: `Notifier`, `TestMessage`, `Channel` protocol, `EmailChannel` (token exchange, Gmail `messages.send`, MIME in memory) |
| `src/jobfinder/worker/{main.py,__main__.py}` | `run_once()`: lease, stale housekeeping, oldest queued run, dispatch by kind, renewal task, release; `__main__` wires real implementations |
| `src/jobfinder/web/{jobs,checks}.py` | new: `JobStarter` (Cloud Run Admin API `:run`, ADC) and fake; routes `POST /checks/a1`, `POST /checks/email`, `GET /checks` returning the card fragment |
| `src/jobfinder/web/app.py` | include the check routes on `protected`; `/static/htmx.min.js` route; inject `runs_repo` and `job_starter` into `create_app` (in-memory in `dev`) |
| `src/jobfinder/web/templates/{base,settings,_checks.html}`, `static/app.css`, `static/htmx.min.js` | htmx script in `base.html` (pinned copy, version in header); Settings page shows the card; fragment with states; card CSS (one column at 360 px, two columns ≥ 768 px, 44 px buttons) |
| `tests/conftest.py` | autouse socket guard (AC20); fixtures for fake runs repo, lease, session, channel, secret reader, job starter |
| `tests/unit/test_{runs_repo,lease,gateway,stop_triggers,email_channel,notifier,worker,checks_routes,secret_reader,page_loads,card_template,socket_guard}.py` | new |
| `tests/unit/test_infra_secrets.py` (or `scripts/tests`) | AC18: parse `secrets.tf` and the two Cloud Run files |
| `docs/changes/71-worker-a1-check-email/plan.md` | Divergence log and Proof filled at the end |

ADRs are not edited. The use case file is unchanged unless wording diverges.

## Steps

1. Commit `plan.md`.
2. **Socket guard first**: autouse fixture in `tests/conftest.py` patches `socket.socket.connect` (localhost, 127.0.0.1 and ::1 allowed, anything else raises); a test proves an outside address raises (AC20). Every later test runs under it.
3. **Domain and repositories** (tests first): `Run`, enums, reason texts; in-memory `RunRepository` and `Lease`, then the Firestore versions with the same contract (transactions for `create_if_none_active` and lease take/renew/release). Tests: AC2, AC3, AC6–AC8 at repository level, `expire_at` = created + 30 days.
4. **Secret reader**: protocol, fake, Secret Manager client (`httpx` with injectable transport). Tests with `httpx.MockTransport`: success, 404, `FAILED_PRECONDITION`, other error (AC21).
5. **Stop triggers and gateway**: `evaluate()` pure function over recorded-style snippets (anonymised, written by hand): login wall, authwall, challenge, 403, normal results; gateway with `FakeSession`, injected `sleep`/`rng`; URL builder (https, linkedin.com, fixed keyword); counter increment and limit; only `browser_navigate` and `browser_snapshot` calls, no `filename` (AC9–AC13).
6. **MCP session**: `McpSession` protocol and the real client; test the headers and the Cloudflare Access 401/403 → `a1_auth` mapping against a local fake streamable-HTTP server on localhost (the one test that opens a socket, allowed by the guard); if the SDK is unusable use the `httpx` JSON-RPC fallback.
7. **Notifier and email channel**: `TestMessage`, `Notifier` calling channels independently; `EmailChannel` over `httpx.MockTransport` (token exchange, send, `invalid_grant` → `email_auth`, other → `email_send_failed`); no recipient, token or body in logs (AC14–AC16).
8. **Worker `run_once()`**: lease, stale-running failure, dispatch, renewal task with an injectable clock, release in `finally`; the `__main__` wiring with real implementations and `SecretReader`; exit code 0 on a normal outcome. Tests: AC6–AC9, AC14–AC16, AC21 end to end with fakes.
9. **Web routes and card**: `JobStarter` + fake; `POST /checks/a1|email` (protected: Origin, IAP, owner), idempotent while active, start failure → `start_error`, no 500; `GET /checks` fragment; vendored htmx and its protected route; template states and CSS; tests for AC1–AC5, AC17, AC22 (`TestClient`, test token fixture, 360 px rules asserted by CSS/markup checks as in `test_pages.py`).
10. **Infra and docs**: `secrets.tf` (`a1-url`), `iam.tf` (`datastore.indexViewer` for `app-plan`, comment updated), worker env, indexes, runbook, architecture; `terraform fmt -check` and `init -backend=false && validate` for both layers; AC18 test.
11. Run `scripts/build.sh`, `scripts/test.sh`, `scripts/lint.sh`, `scripts/audit.sh` (CI) and paste the output; run the `verifier` subagent and quote its verdict. Open the PR with `Refs #71` (not `Closes`) on the owner's go-ahead: AC19 is proven only after deploy.
12. **Owner actions, in this order** (the platform change is in this PR, so it cannot be applied before the merge; the deploy does not depend on it because no Cloud Run resource references a secret): merge → the owner applies `infra/platform` (the `a1-url` container with the worker's accessor, and `roles/datastore.indexViewer` for `app-plan`) → the owner adds the `a1-url`, `a1-client-id`, `a1-client-secret` and `email-sender` values (prerequisites in the spec) → AC19. The checks report *not configured* until each value exists; until `indexViewer` is applied `app-plan` and drift fail with permission denied on the new indexes.
13. After deploy: AC19 (press "Check A-1" → successful snapshot; press "Send test email" → message arrives; screenshots at 360 and 1280 px; logs and run documents contain no address or host) is recorded in Proof by a follow-up Proof PR with `Closes #71`, as for #69 and #70. The verifier lists AC19 as pending until then.

## Risks

| Risk | Mitigation |
|---|---|
| Cloud Run rejects a job update that references a secret without a version | No secret refs anywhere; the worker reads at execution time (AC18, AC21) |
| `a1-url` container missing at deploy | Nothing in the app layer references it; the worker gets `NotConfigured` until the owner applies `infra/platform` after the merge and adds the value; order in step 12 |
| `app-plan` lacks `indexViewer` once the indexes merge | Role added in `iam.tf` in this PR; owner applies it right after the merge (step 12); until then `app-plan` and drift show permission denied |
| `mcp` SDK does not support Python 3.14 or fails `pip-audit` | Fallback: a minimal JSON-RPC-over-HTTP client behind `McpSession` (same tests); decide at step 6 and note it in the Divergence log |
| Firestore transactions (lease, `create_if_none_active`) are tested only with fakes | Keep the Firestore code small and mirror the contract tests; first real exercise is AC19; the lease only matters for concurrent executions |
| Composite indexes missing → query fails at runtime | Indexes in `infra/app/indexes.tf` (deployer has `indexAdmin`); `latest(kind)` uses the index; active check reads `latest` so no third index |
| LinkedIn shows an authwall or changes the page → false failure | Distinct reasons (`login_wall`, `challenge`, `empty_snapshot`) so the card says what to do; one page, no retry |
| Repeated presses hit LinkedIn | Duplicate guard while active, daily limit of 150, one page per run; no cooldown (accepted concern 4) |
| Cold start of the worker with Secret Manager, Gmail and MCP imports | Lazy imports per kind; a run takes seconds; measure once in AC19 |
| Gmail refresh token invalid after a password change | `email_auth` reason with re-consent text; runbook already covers it (ADR-0010) |
| A log line or error message leaks the A-1 host, token or address | Log only the reason code and exception class; AC16 test with `caplog` on fake secrets |
| Hook blocks edits that mention a secrets folder path | Docs and code name secrets by id, not by folder path |

## Proof

| Acceptance criterion | Evidence |
|---|---|
| AC1 | `test_card_template.py`: Settings shows both buttons and "Not run yet" |
| AC2, AC3 | `test_checks_routes.py` + `test_runs_repo.py`: one run, job starter called once; second press creates none |
| AC4 | `test_checks_routes.py`: failing fake starter → run stays queued, card text, status 200 |
| AC5 | `test_checks_routes.py`: no token, wrong account, missing and foreign Origin → 401/403, no run |
| AC6, AC7, AC8 | `test_worker.py` + `test_lease.py`: lease taken and released; second worker exits; stale run failed `worker_crashed` |
| AC9, AC10 | `test_gateway.py`: fake session calls recorded; result, snapshot size, counter +1, injected sleep |
| AC11, AC12, AC13 | `test_stop_triggers.py`, `test_gateway.py`, `test_mcp_session.py`: reasons per page, `a1_auth`, `daily_limit` |
| AC14, AC15 | `test_email_channel.py`, `test_worker.py`: fake channel receives one message; error codes mapped |
| AC16 | `test_worker.py`, `test_email_channel.py`: `caplog` and stored documents contain none of the fake secrets, address, host or text |
| AC17 | `test_card_template.py`: states at 360 px rules, 44 px buttons, text status |
| AC18 | `scripts/check_infra.py` (run by `scripts/lint.sh`) with `tests/scripts/test_check_infra.py`: readers of the four secrets are `worker` only; no reference to them in any `infra/app` file; `terraform fmt -check` here, `terraform validate` by CI `app-plan` |
| AC19 | Post-deploy screenshots and the arrived message, recorded in a follow-up Proof PR (pending until then) |
| AC20 | `conftest.py` socket guard + `test_socket_guard.py`; full `scripts/test.sh` output |
| AC21 | `test_secret_reader.py`, `test_worker.py`: missing secret/version → `a1_not_configured` / `email_not_configured`, gateway never created |
| AC22 | `test_card_template.py`, `test_routes.py`: htmx from `/static/htmx.min.js`, no external host; unauthenticated request refused |

Commands: `scripts/build.sh`, `scripts/test.sh`, `scripts/lint.sh`, `scripts/audit.sh`, `terraform -chdir=infra/{platform,app} validate`.

## Divergence log

- **No `mcp` SDK.** `McpSession` is implemented by a small synchronous Streamable HTTP client over `httpx` (`browser/mcp_session.py`), the plan's fallback chosen up front: the SDK is async and heavy, and the protocol needs only `initialize`, `notifications/initialized` and `tools/call`. No dependency was added (`pyproject.toml` and `uv.lock` are unchanged), so `pip-audit` has nothing new to report. Its tests use `httpx.MockTransport` instead of a local fake server, so no test opens a socket.
- **Two reason codes added** to the spec's table: `off_policy` (the browser ended on another host) and `internal_error` (any unexpected exception in a run, recorded without details).
- **New helper modules:** `jobfinder/gcp.py` (ADC access token, used by the secret reader and the job starter); `SettingsRepository.notification_email()` for the worker.
- **`email-sender` JSON keys** are `client_id`, `client_secret`, `refresh_token`, `sender` (documented in the runbook step 5).
- **Worker environment:** `JOBFINDER_ENVIRONMENT` and `JOBFINDER_PROJECT_NUMBER` (the secret reader needs the project number); no secret references.
- **Worker `dev` mode** uses in-memory dependencies, so the CI image smoke test (`docker run ... python -m jobfinder.worker`) and `test_worker_starts` need no Firestore; `.github/workflows/ci.yml` passes `-e JOBFINDER_ENVIRONMENT=dev`.
- **`scripts/check_a1.py`** allows the one runtime file and its test that use the Cloudflare Access header names (`browser/mcp_session.py`, `tests/unit/test_mcp_session.py`); the rule's own text said the runtime would be allowed once it existed.
- **AC18** is enforced by `scripts/check_infra.py` (run by `scripts/lint.sh`) with tests in `tests/scripts/test_check_infra.py`, not by `tests/unit/test_infra_secrets.py`.
- **Lease loss** writes one final record for its own run (`stopped`, `lease_lost`) and then exits; the ADR-0007 gap (a stalled worker may write for up to one renewal interval) is accepted as written.
- **Retention:** run records 30 days; `page_loads` documents 365 days (ADR-0007: 12 months).
- **Not run in this session** (sandbox limits): `terraform init`/`validate` (provider download blocked) and `scripts/audit.sh` (read-only cache directories). `terraform fmt -check` passes on both layers; the CI `app-plan` validates the app layer.
- **Index viewer for `app-plan` (found in the owner's platform apply):** `roles/datastore.indexViewer` does not exist in GCP ("not supported for this resource"); ADR-0009's "datastore index viewer" is implemented as a custom role `indexViewer` with `datastore.indexes.get` and `datastore.indexes.list` only (no data access), as for `stateLister`.

