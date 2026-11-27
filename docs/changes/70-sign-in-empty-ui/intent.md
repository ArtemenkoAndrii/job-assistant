# Intent: Sign-in and empty UI (skeleton 2/3)

| | |
|---|---|
| **Issue** | #70 (slice 2 of the walking skeleton, epic #22) |
| **Author** | ArtemenkoAndrii (owner); drafted by Claude |
| **Status** | Accepted |
| **Date** | 2026-11-27 |

## Problem

The deployed `jobfinder-web` answers only `/health`. IAP protects it, but the app itself does not check who is calling: if IAP were bypassed or misconfigured, every route would be open, and nothing yet proves that only the owner's account gets in (ADR-0008, NFR-S1). The app has no page the owner can sign in to, no record of the owner on first sign-in (UC-01 step 2), and no UI shell that works on a phone. Every later slice (settings, profiles, runs) needs these as its base.

## Proposed outcome

- The owner opens the app on a phone and on a laptop, signs in through Google and IAP, and lands on the empty profiles page. Any other Google account is refused.
- The app verifies IAP's signed token on every route except `/health`, compares the verified email with the owner's address, and refuses everything else: no token, a token for another audience, or another account. A cross-origin or origin-less state-changing request is refused too.
- The owner's address comes from the `owner-email` secret (ADR-0008). If it is empty or unreadable, the app refuses everyone (fail closed).
- On the owner's first sign-in the app creates `settings/owner` in Firestore and takes the sign-in email as the notification email (UC-01). The record is a result of signing in, never a condition for it.
- The page shell has a header with a "Sign out" link to IAP's `/_gcp_iap/clear_login_cookie`.
- The landing page is the empty profiles page; settings and runs are empty placeholder pages. All are readable and usable at 360 px and on desktop, in English.
- Auth behaviour is covered by automated tests: no token, wrong audience, other email, cross-origin POST, and dev mode on Cloud Run.

## Affected users and systems

- Users: the owner, on a phone and on a laptop. No other users in the MVP.
- Systems: `jobfinder-web` (auth dependency, Origin check, page shell), Firestore (`settings/owner`), Secret Manager value `owner-email`, the web service's environment configuration in `infra/app`.
- Use cases: UC-01 (Sign in).

## Constraints

- Accepted ADRs: 0008 (IAP, app-side JWT and owner check, Origin check, dev mode rules), 0005 (FastAPI, Jinja2, htmx, one image), 0007 (Firestore, `settings/owner`), 0006 (Cloud Run, secrets).
- NFR-S1 (every route authenticated), NFR-P6 (no email or token in logs), NFR-U1 (360 px and desktop), NFR-U4 (accessibility), NFR-C1 (no new paid resources).
- The `owner-email` value is already in Secret Manager (runbook step 5); this slice can rely on it and needs no new runbook step for it.
- The repo is public: no owner email, project number or personal data in the diff or in test fixtures.
- Tests never reach Google or a real token endpoint; they use a test signing key.

## Out of scope

- Settings editing (UC-02), profiles (UC-03/04), runs and any real page content: slice S1 and later.
- The A-1 snapshot call (slice 3).
- Terraform for IAP and the OAuth client (done in #69); new infrastructure beyond passing configuration to the service.
- Roles or additional users.

## Open questions

None.
