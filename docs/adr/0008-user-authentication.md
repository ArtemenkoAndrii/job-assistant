# ADR-0008: User authentication

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #17 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

The web app runs as a Cloud Run service on `*.run.app` in the GCP project `job-finder` ([ADR-0006](0006-hosting.md)). Every page and API must require sign-in, and the MVP admits only the owner's account (NFR-S1, UC-01 A2). Sign-in must work on a phone and a laptop (NFR-U1). Vision §10: "as simple as possible to implement, but reliable enough".

Owner input: the GCP account is **personal, without a Google Cloud organization**, and the owner signs in with a **personal Gmail account**. There is no custom domain.

The worker and Cloud Scheduler do not sign in as users; they use service accounts (ADR-0006).

## Decision drivers

- Least code to write and get wrong: no password storage, no session or token handling of our own if avoidable (NFR-S1, NFR-S2).
- Works with a personal Gmail account and a project without an organization; on `*.run.app`.
- Free (NFR-C1).
- The allowed account is personal data and must not be in the public repo.
- Testable locally and in CI without Google sign-in (NFR-M5).

## Options considered

### Option 1: Identity-Aware Proxy (IAP) directly on the Cloud Run service

Google's proxy in front of the service: the user signs in with their Google account, IAP checks that the account has access, and only then forwards the request. Direct IAP on Cloud Run is generally available (Google Cloud release notes, March 2026), needs no load balancer and costs nothing. It protects every ingress path, including the default `run.app` URL. A project without an organization needs a one-time custom OAuth client (audience **External**).

- Good: no sign-in, session or logout code in the app; Google handles passwords, 2-step verification and suspicious sign-ins; the allowed account is an IAM binding.
- Good: the app gets the user's identity in a signed header, `x-goog-iap-jwt-assertion`, and verifies it as a second line of defence if IAP were ever bypassed or disabled.
- Bad: GCP-specific; moving to another platform needs a new sign-in solution. Local development needs a stand-in for the header.

### Option 2: "Sign in with Google" in the app (OpenID Connect, e.g. Authlib)

- Good: portable to any host.
- Bad: we write the login redirect, callback, state and nonce checks, signed session cookies, logout and session expiry — more security-sensitive code; a session signing key to manage.

### Option 3: Firebase Authentication / Identity Platform

- Good: free tier, many sign-in providers.
- Bad: a JavaScript SDK in the browser plus token verification on the server — a front-end dependency the stack avoids (ADR-0005); still our own session handling.

### Option 4: Username and password

- Bad: password storage and reset; weaker than Google sign-in with 2-step verification. Rejected.

## Decision

**Option 1: IAP directly on the `jobfinder-web` Cloud Run service.**

1. **Access:**
   - IAP is enabled on the service with a custom OAuth client: audience External, publishing status **In production** (IAP asks only for basic profile and email, which need no Google verification; "Testing" would force frequent re-sign-in).
   - The owner's Gmail account gets **IAP-secured Web App User** on the service; nobody else does.
   - Only the IAP service agent has `roles/run.invoker` on `jobfinder-web`; `allUsers` never does (no `--allow-unauthenticated`).
   - The owner's address is a Terraform variable marked `sensitive`, its value in a GitHub Actions secret, the Terraform state in a private bucket (#16). The repo and the public CI logs never show it.
2. **Defence in depth in the app** (a FastAPI dependency on every route, NFR-S1):
   - verify `x-goog-iap-jwt-assertion`: algorithm **ES256** only; keys from `https://www.gstatic.com/iap/verify/public_key-jwk`; `iss` = `https://cloud.google.com/iap`; `aud` = `/projects/<PROJECT_NUMBER>/locations/us-central1/services/jobfinder-web` (project number, from configuration); `exp`/`iat` with ≤ 30 s clock skew;
   - take the email from the verified token, never from the unsigned `x-goog-authenticated-user-email` header;
   - compare it, lowercased, with `JOBFINDER_OWNER_EMAIL` (a Secret Manager value) and answer **403** if it differs (UC-01 A2). If the setting is missing or empty, **everyone** is denied (fail closed);
   - any request without a valid token → 401;
   - 401/403 responses and logs never contain the email or the token (NFR-P6).
   - The only route without this check is `/healthz`, which returns just the status and version; in the deployed service it is still behind IAP, so nothing is public. It lets the CI smoke test and Cloud Run probes reach the container.
3. **First sign-in (UC-01 step 2):** if `settings/owner` does not exist, it is created with the signed-in email as the notification email.
4. **Sessions:** IAP keeps the session in its own cookie; the app stores no session. Sign-out is the Google account sign-out.
5. **CSRF:** every method other than GET, HEAD and OPTIONS must carry an `Origin` header that is in a configured list of the service's URLs (Cloud Run serves a deterministic `…-<number>.us-central1.run.app` URL and an older hash URL; both are listed, or one is disabled in #16). A missing or other `Origin` → 403. GET handlers have no side effects. IAP cookies are sent by the browser automatically, so this check is required.
6. **Local development and tests:**
   - Tests replace the auth dependency with FastAPI `dependency_overrides`; production code has no bypass flag for tests.
   - Local runs use `JOBFINDER_ENVIRONMENT=dev` for a fixed stand-in identity. The default when unset is production, and the app refuses to start in `dev` when `K_SERVICE` is set (it runs on Cloud Run).
   - Tests cover: no token → 401; wrong `aud`, `iss`, algorithm or an expired token → 401 (tokens signed with a test key); other email → 403; empty owner setting → 403; owner → 200; cross-origin or missing-Origin POST → 403; `dev` with `K_SERVICE` → startup error.

**Secrets (ADR-0006):** the owner email moves into Secret Manager; the "session key" planned in ADR-0006 is not needed (IAP keeps the session). The OAuth client secret is stored by IAP itself.

**Cost:** IAP for Cloud Run is free; no load balancer.

Out of scope: email delivery (#21); Terraform and CI setup of IAP and the OAuth client (#16); other users or roles (post-MVP).

**Use case UC-01** is updated: sign-in, a cancelled sign-in (A1) and a non-owner account (A2) are handled by Google and IAP pages; the app's own 403 applies only if IAP is bypassed.

## Consequences

- Positive: no login, session or password code in the product; Google provides 2-step verification and account protection; works on any phone or laptop browser.
- Positive: two independent checks — IAP and the app's own JWT verification with the owner email.
- Negative: tied to GCP; a different host needs a new sign-in ADR (Option 2 is the fallback).
- Negative: the first IAP enablement in a project without an organization needs a one-time step in the Cloud Console (custom OAuth client, External audience); documented as a manual step in #16.
- Negative: development uses a stand-in identity; the deployed service must never run in `dev` mode — guarded by a startup check and a test.
- Follow-ups:
  - #16: IAP on the service, OAuth client (one-time Console step), the owner's IAP role, invoker only for the IAP service agent, `JOBFINDER_OWNER_EMAIL` secret (replaces ADR-0006's "session key"), sensitive Terraform variable, private state.
  - #22: the auth dependency, its tests, deployed sign-in on a phone and a laptop (UC-01).
  - #21: email delivery can now be chosen.
