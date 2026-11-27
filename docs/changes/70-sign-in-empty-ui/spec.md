# Spec: Sign-in and empty UI (skeleton 2/3)

| | |
|---|---|
| **Issue** | #70 (epic #22) |
| **Intent** | [intent.md](intent.md) |
| **Status** | Accepted |
| **Date** | 2026-11-27 |

<!-- Written with the writing-specs skill; policy skills applied: security-privacy, cost-guard, mobile-first-ux. resume-rules does not apply (no resumes, skills or answers). -->

## Related ADRs

- [ADR-0008](../../adr/0008-user-authentication.md): IAP in front; the app verifies the IAP JWT (ES256, issuer, audience, expiry) and the owner email on every route except `/health`; fail closed; Origin check on state-changing methods; `dev` mode rules; first sign-in creates `settings/owner`. This spec implements §2–§6 of its decision, except that the Origin check compares with the request's own host instead of a configured list (see *Flagged concerns* 2).
- [ADR-0007](../../adr/0007-data-storage.md): `settings/owner` lives in Firestore; no TTL (kept until deleted).
- [ADR-0005](../../adr/0005-application-stack.md): FastAPI, server-rendered Jinja2, no front-end build step.
- [ADR-0006](../../adr/0006-hosting.md): Cloud Run service `jobfinder-web` runs as service account `web`, which already reads `owner-email` and uses Firestore.

One point differs from the ADR's wording (the Origin rule) and is listed under *Flagged concerns* with a proposed resolution.

## Requirements

### Functional

| ID | Requirement | Use case |
|---|---|---|
| R1 | Every route except `/health` runs an auth check before its handler. The check reads `x-goog-iap-jwt-assertion` and accepts it only if: algorithm is ES256; signature verifies against the keys published at `https://www.gstatic.com/iap/verify/public_key-jwk` (selected by `kid`); `iss` is `https://cloud.google.com/iap`; `aud` is `/projects/<project number>/locations/us-central1/services/jobfinder-web`; `exp` and `iat` are valid with at most 30 s clock skew. Any failure, or a missing header, answers **401**. | UC-01 |
| R2 | The email is taken only from the verified token, never from `x-goog-authenticated-user-email`. It is compared, lower-cased, with the owner email from the `owner-email` secret (environment `JOBFINDER_OWNER_EMAIL`). A different email answers **403**. | UC-01 A2 |
| R3 | If the owner email is empty or unreadable, the app answers 403 to every request except `/health` (fail closed). Whether `settings/owner` exists plays no part in this decision. | UC-01 A2 |
| R4 | Any method other than GET, HEAD, OPTIONS must carry an `Origin` header equal to `"https://" + Host` of the same request (host compared case-insensitively; `X-Forwarded-Host` is not used), else **403**. A missing `Origin` is 403. The check runs for all such requests, including unauthenticated ones, and works on either Cloud Run URL of the service without configuration. GET handlers have no side effects. | UC-01 |
| R5 | After a successful auth check, if `settings/owner` does not exist it is created with the sign-in email as the notification email. Creation is idempotent: concurrent first requests produce one record and never overwrite an existing one. A failure to read or create the record does not turn an authenticated owner away from the page, and is logged without the email. | UC-01 step 2 |
| R6 | The page shell has a header with the product name, navigation to Profiles, Settings and Runs, and a **Sign out** link to `/_gcp_iap/clear_login_cookie` (handled by IAP, not by the app). The link clears only IAP's cookie; the Google session stays, so the next visit may sign the owner in again silently. This is expected behaviour, not a bug. | UC-01 |
| R7 | `GET /` redirects to `/profiles`. `/profiles` (landing), `/settings` and `/runs` are placeholder pages with an empty state and no data. | UC-01 step 3 |
| R8 | `JOBFINDER_ENVIRONMENT` defaults to production when unset. In `dev` the app uses a fixed stand-in identity and skips the JWT check; the app refuses to start in `dev` when `K_SERVICE` is set. Production code has no other bypass; tests use FastAPI `dependency_overrides` or tokens signed with a test key. | NFR-S1 |
| R9 | 401 and 403 responses are plain generic pages. Neither responses nor logs contain the email, the token or the owner setting. | NFR-P6 |
| R10 | The service receives its configuration through `infra/app`: project number, the `owner-email` secret (version `latest`) as `JOBFINDER_OWNER_EMAIL`, and `JOBFINDER_ENVIRONMENT=production`. There is no allowed-origins setting. | ADR-0008 |

### Non-functional

- NFR-S1: every route except `/health` requires the owner (R1–R3); the route inventory test enforces it.
- NFR-S2: the owner email comes only from Secret Manager at runtime; it is in no code, fixture, image or log.
- NFR-P1: the only personal data stored is the owner's email in `settings/owner`.
- NFR-P6: no email or token in logs or responses (R9).
- NFR-U1, NFR-U4, NFR-U5: pages work at 360 px and on desktop, are accessible, in English (see UX).
- NFR-U3: the empty pages are light (no JavaScript, one small stylesheet).
- NFR-A1: cold start stays ≤ 10 s with the Firestore client and key fetch added (AC18; baseline from #69: 4.0 s, 58 MB image).
- NFR-M5: tests make no network call; keys and Firestore are faked.

## Acceptance criteria

- **AC1** — Given a request to `/profiles` without `x-goog-iap-jwt-assertion`, when it is handled, then the answer is 401.
- **AC2** — Given tokens that are otherwise valid but have a wrong `aud`, a wrong `iss`, a non-ES256 algorithm (including `none` and HS256), a bad signature, an unknown `kid`, or an expired `exp`, when each is sent, then every answer is 401.
- **AC3** — Given a valid token for an email different from the owner's, when the request is handled, then the answer is 403, and a spoofed `x-goog-authenticated-user-email` carrying the owner's address changes nothing.
- **AC4** — Given a valid token for the owner (compared case-insensitively), when `/profiles` is requested, then the answer is 200 with the profiles empty state.
- **AC5** — Given the owner email setting is empty or missing, when the owner's valid token is sent, then the answer is 403, even if `settings/owner` exists.
- **AC6** — Given a valid owner token and a POST with a foreign `Origin`, or with no `Origin`, when it is handled, then the answer is 403. A POST without a token and with a foreign `Origin` is also 403. Given an `Origin` equal to `https://` + the request's `Host`, the request reaches its handler, for the deterministic URL host and for the hash URL host alike; an `Origin` that matches only `X-Forwarded-Host` is refused.
- **AC7** — Given `JOBFINDER_ENVIRONMENT=dev` and `K_SERVICE` set, when the app starts, then startup fails with an error; given the variable unset, then the app runs in production mode and demands a token.
- **AC8** — Given every route registered in the app, when each is requested without a token, then all answer 401 except `/health`, which answers 200 with only status and version.
- **AC9** — Given the owner signs in and `settings/owner` does not exist, when the first page is served, then the record exists with the sign-in email as notification email; given it exists with another notification email, then it is left unchanged; given two concurrent first requests, then one record exists.
- **AC10** — Given Firestore is unavailable on the first request, when the owner opens `/profiles`, then the page still answers 200 and the failure is logged without the email.
- **AC11** — Given the 401 and 403 responses of AC1–AC6 and the captured logs, when they are searched, then neither the owner's email, another email, nor the token text appears.
- **AC12** — Given any page, when it is rendered, then the header contains a "Sign out" link to `/_gcp_iap/clear_login_cookie`, and `GET /` redirects to `/profiles`.
- **AC13** — Given the rendered `/profiles`, `/settings` and `/runs`, when a template test inspects them, then each has the viewport meta tag, the document language, `header`, `nav` and `main` landmarks, the Sign out link, and the current page marked in the navigation.
- **AC14** — Given the rendered pages and the stylesheet, when a test inspects them, then every interactive element has a text label, the stylesheet defines a visible focus style, and it sets a minimum size of 44×44 px for links and buttons in the header.
- **AC15** — Given the deployed pages, when the owner takes screenshots at 360 px and at 1280 px, then at 360 px there is no horizontal scrolling and the header, navigation and Sign out link are reachable, and at 1280 px the content is a bounded, centred column with the navigation inline. *Manual screenshots in the PR, with AC16.*
- **AC16** — Given the deployed service, when the owner signs in on a phone and on a laptop, then the profiles page opens on both; when any other Google account tries, then it is refused (by IAP, or with 403 by the app). *Manual evidence in the PR.*
- **AC17** — Given `infra/app`, when `terraform validate` runs, then the service defines the environment variables of R10, with the owner email taken from Secret Manager and no value in the repository.
- **AC18** — Given this slice is deployed and the service has been idle for 15 minutes, when the owner opens `/health` through IAP, then cold start from Cloud Run's `container/startup_latencies` metric is ≤ 10 s; the measured cold start and the image size are recorded in `plan.md` → Proof next to the #69 baseline (4.0 s, 58 MB). If the Firestore client pushes either far above the baseline, the result goes to the owner before merge.

## Design

**Flow.** Request → Origin check (non-safe methods) → auth dependency → owner bootstrap → handler. `/health` is the only route registered without the dependencies; the dependencies are attached to the router(s) that hold all other routes, so a new route is protected by default. The route inventory test (AC8) fails if one is not.

**Components (`jobfinder.web`, `jobfinder.storage`, `jobfinder.config`).**
- Settings: `environment` (default production), `owner_email`, `project_number`, `allowed_origins`. The startup guard for `dev` plus `K_SERVICE` is in the application factory.
- Auth: verifies the token and returns the verified identity. IAP public keys are fetched lazily on first use, cached in process with a time limit, with a short timeout; any failure to obtain keys is a 401 (fail closed). A `kid` not in the cache triggers at most one refresh.
- Settings repository: a small interface with an in-memory fake and a Firestore implementation; `ensure_owner(email)` creates `settings/owner` only if absent (create-if-absent semantics). The app remembers in process that it has succeeded, so Firestore is touched once per instance, not once per request.
- Origin check: a dependency on all non-safe methods; it compares `Origin` with `"https://" + Host` of the request. The browser sets `Origin` and a cross-site page cannot make it equal to the service's own host, so no URL list is needed and both Cloud Run URLs work.

**Configuration (R10).** Project number comes from the existing `project_number` Terraform variable. The owner email is a Cloud Run secret environment variable (version `latest`), read once when an instance starts; a changed secret value takes effect after the next deploy or an instance restart, not on the next request.

**Pages.** `base` template with header (name, nav, Sign out), main landmark, footer-free; three child templates with empty states; generic 401/403 templates. One small hand-written stylesheet served by the app (static files are under the same auth). No JavaScript.

**Data.** `settings/owner`: notification email, plus the fields later slices add (re-apply period, kill switch). This slice writes only the notification email and `created_at`.

## Security, privacy and cost

- Security:
  - NFR-S1: auth and Origin checks are attached by default; the route inventory test makes an unprotected new route fail CI. `/health` returns only status and version.
  - Token checks are as strict as ADR-0008 (ES256 only, `iss`, `aud`, `exp`/`iat`, `kid`); the unsigned email header is never used. Missing or empty owner setting denies everyone.
  - CSRF: IAP cookies are sent automatically, so the Origin check on non-safe methods is required (R4). `Host` is not an extra trust input here: only the equality of the browser-set `Origin` with the request's own host matters. Sign out is a GET to IAP's own endpoint and is not state-changing for the app.
  - NFR-S2: the owner email is read from Secret Manager; no new secret. `dev` mode cannot start on Cloud Run (R8).
  - New outbound call: one HTTPS GET to `www.gstatic.com` for IAP's public keys at runtime. Cloud Run has open egress; no dev-container domain is added because tests use a test key.
  - New dependencies (JWT/crypto library, Firestore client, an HTTP client for key fetch) must be maintained and pass `pip-audit` (NFR-S7).
  - NFR-S6, NFR-S8, NFR-B*: no agents, browser or job-board credentials in this change.
- Privacy:
  - NFR-P1: stores the owner's account email in `settings/owner` as the notification email; nothing else personal. Retention NFR-P3: kept until deleted (ADR-0007); NFR-P4 does not apply (no profile data).
  - NFR-P6: no email or token in responses or logs (R9, AC11). Nothing is sent to the LLM (NFR-P5).
  - NFR-P7: test fixtures use invented addresses (such as `owner@example.test`), never the real one; the test signing key is generated in the test.
- Cost: no LLM calls: +$0.00 per run. Cloud: no new resource; Firestore does one read and at most one write per instance start (far inside the free tier), one small key fetch per cold instance, secret access is a single read per start. Effect on NFR-C1: none. A larger image only affects Artifact Registry storage, which keeps the last 3 images (AC18 records the size).

## UX

Screens: **Profiles** (landing), **Settings**, **Runs**, plus generic 401/403 pages.

- Header: product name, then navigation (Profiles, Settings, Runs), then **Sign out**. At 360 px the header wraps onto two rows (name and Sign out on the first, navigation on the second) with no horizontal scroll; on desktop it is one row.
- Each page: a title and one plain-language empty state, for example "No profiles yet. Profiles will appear here." (no use-case or NFR IDs in the UI text). No primary action exists yet, so none is promised; "New profile" arrives in slice S1.
- States: empty (all three pages); error (401/403 pages say "You can't open this page" and give no detail, with no email); loading and partial data do not occur yet.
- Mobile 360 px: single column, text size at least 16 px, touch targets at least 44×44 px, no hover-only actions. Desktop 1280 px: content in a centred column of bounded width, navigation inline.
- Accessibility: landmarks (`header`, `nav`, `main`), the current page marked in the navigation, visible keyboard focus, AA contrast, document language set, viewport meta tag.
- Speed: server-rendered HTML and one small stylesheet; no JavaScript.
- Language: English.

## Flagged concerns

1. **Default environment.** ADR-0008 says the default when `JOBFINDER_ENVIRONMENT` is unset is production; the current `config.py` defaults to `dev`. This spec follows the ADR (R8), so the default changes in code, and local runs need `JOBFINDER_ENVIRONMENT=dev` set explicitly. *Agreed by the owner.*
2. **Origin rule vs ADR-0008 §5.** ADR-0008 says `Origin` must be in a configured list of the service's URLs; this spec uses `Origin == "https://" + Host` (R4), because the owner uses the hash URL and a deterministic-only list would refuse it. The behaviour is equal or stricter in intent, but the ADR text differs and a spec must not contradict an accepted ADR. **Proposed resolution:** the owner decides whether to amend ADR-0008 §5 (a short superseding ADR or an accepted edit) in this PR before `plan.md` is approved; the spec is accepted on that understanding. `/healthz` in the ADR is left as is: the rename to `/health` is in #69's Divergence log.
3. **Sign out in dev.** `/_gcp_iap/clear_login_cookie` exists only behind IAP; in local `dev` mode the link leads to a 404. *Accepted by the owner.*

## Out of scope

- Settings editing, profiles, runs: slice S1 and later. The placeholder pages show no data.
- The A-1 snapshot call (slice 3), Terraform for IAP and the OAuth client (#69), roles or other users, a logout endpoint of our own, session handling in the app.
- An automated screenshot and Lighthouse pipeline for NFR-U1/U3/U4 in CI: AC13–AC14 are template and stylesheet tests, AC15 is manual screenshots in the PR.
