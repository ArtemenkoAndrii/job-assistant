# ADR-0010: Email delivery

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #21 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

Job Finder sends a few emails, all to one recipient, the owner:
- **Summary** after a run with at least one package (UC-09). It is sent at most 10 minutes after the run ends (NFR-R4).
- **Alerts**: a blocked run (UC-08), a failed run, the budget alert, a restriction notice (NFR-O2).

Volume is a few emails a week; the worst case is a few a day. Email *applications* are out of the MVP (#4).

Constraints:
- **No custom domain** (owner input for ADR-0006). We cannot set up SPF, DKIM or DMARC for a domain of our own.
- **The owner signs in with a personal Gmail** (ADR-0008), which is also the notification email (UC-01 step 2).
- **The worker sends the mail.** It runs on Cloud Run (ADR-0006) and reads secrets from Secret Manager (NFR-S2).
- **Personal data:** an email must not carry resume content; it carries titles, companies and links to the web app (ADR-0006, NFR-P6).
- **Cost:** hosting ≤ $5/month (NFR-C1).

## Decision drivers

- The email reaches the owner's inbox, not spam, without a domain.
- The credential the worker holds can do as little as possible.
- Free; few moving parts; testable without sending real mail (NFR-M5).

## Options considered

### Option 1: Gmail API, the owner's account sends to itself, scope `gmail.send` only

The worker calls the Gmail API over HTTPS with an OAuth refresh token for the owner's account. `gmail.send` is a *sensitive* scope that allows sending messages only, with no read or modify rights on the mailbox.

- **Good: deliverability.** The mail is sent from the owner's own Gmail to the same Gmail. Google signs it, the sender is the recipient's own account, and no domain is needed.
- **Good: narrow credential.** A leaked token can send mail as the owner but cannot read the mailbox. The token can be revoked at any time in the Google account settings.
- **Good: free and simple to run.** It uses HTTPS from Cloud Run, so there are no SMTP ports or relays.
- **Verification.** Apps that request sensitive scopes normally need Google verification, but **personal use** is one of the listed exceptions. The owner sees an "unverified app" screen once, on their own consent.
- **Bad: one-time consent and a refresh token to keep.** The consent screen must be **In production**. External apps in *Testing* get refresh tokens that expire after 7 days. Changing the Google password can also revoke the token (see Consequences).

### Option 2: Gmail SMTP with an app password

Personal accounts with 2-Step Verification can create a 16-character app password and send through `smtp.gmail.com` on port 587 or 465, up to 500 messages a day.

- **Good:** the simplest code; the same deliverability as Option 1.
- **Bad: far too much power.** Google itself calls app passwords "not recommended". Anyone with the code has full SMTP access to the account, and an app password cannot be limited to specific actions; with IMAP it can also read the whole mailbox. That is far more than a worker needs. Rejected.

### Option 3: A transactional email service (Brevo, Mailjet, Resend, …) on its free tier

- **Good:** built for application email; webhooks and logs.
- **Bad:** without a domain we would send "from" a `gmail.com` address through someone else's servers. That fails DMARC alignment, so it is likely to land in spam or be rejected, and some services refuse it outright.
- **Bad:** a second provider, account and API key.
- **Revisit** if the product gets a domain or other users.

### Option 4: Another channel (push, Telegram bot)

- Out of the use cases (UC-09 says email). It may be a later addition, but it does not replace email.

## Decision

**Option 1: the Gmail API with scope `gmail.send` only, the owner's Gmail sending to itself.**

1. **OAuth client.** One OAuth client, "Job Finder mailer", in the `job-finder` project:
   - type *Web application*, separate from the IAP client (ADR-0008);
   - consent screen External, publishing status **In production**, not verified (personal use);
   - scope `https://www.googleapis.com/auth/gmail.send`, nothing else.
2. **One-time consent (owner, manual).** The owner grants the scope once with their Gmail, in Cloud Shell or with the OAuth Playground using our own client. This step goes into the runbook in #22. The result is a refresh token.
3. **Secret.** One Secret Manager secret, `gmail-sender`, holds a JSON value with the client id, the client secret and the refresh token. It is the "email key" planned in ADR-0006, so the project still has 5 secrets. Only the `worker` service account can read it. The value is added by the owner (ADR-0009) and never goes through the repo, CI or Terraform.
4. **Sender and recipient.**
   - "From" is the owner's Gmail; "To" is the notification email in `settings/owner`, by default the same address (UC-01).
   - The worker sends only to that address. There is no code path that sends to anyone else (tested).
   - The subject starts with `[Job Finder]`, so the owner can filter the mail.
5. **Content.**
   - **Summary:** profile name, run date, counts, and for each package its title, company, channel and a link to the package page.
   - **Alert:** the reason and a link to the run.
   - Never resume text, answers, cover notes or dossier facts (NFR-P6).
   - Plain text plus simple HTML; no external images or tracking.
6. **Code.** `jobfinder.notify` has an interface `Mailer` with two implementations:
   - `GmailApiMailer`: Gmail API over HTTPS. It refreshes the access token from the refresh token and keeps nothing on disk.
   - `FakeMailer`: records messages for tests.
   
   Sending runs after the packages are stored (NFR-R5, ADR-0007 write order). One failed send is retried twice with a backoff, and the result is recorded on the run.
7. **When sending fails.** If the token was revoked or has expired, nothing can be emailed, so the alert cannot be an email. Instead:
   - the run record gets `email: failed (reason)`;
   - the web app shows a banner: "Email delivery is not working — re-authorise". The run itself still counts as completed;
   - the runbook has a short re-consent procedure.

**Deliverability (the issue's SPF/DKIM question).** The mail is sent by Gmail for a `gmail.com` address, so Google's own SPF and DKIM sign it and DMARC aligns. We have no domain to configure. If the product gets a domain later, the choice is revisited (Option 3).

**Limits and cost.** Gmail API quotas are far above a few emails a day; the API is free.

Out of scope:
- email *applications* (#32);
- other recipients or a custom domain;
- push or chat notifications.

## Consequences

- Positive: reliable delivery to the owner's inbox with no domain and no extra provider; free.
- Positive: the worker's credential can only send mail; it cannot read the mailbox. It sits in a secret that only `worker` can read.
- Negative: the token can stop working: if the owner revokes it, after some security events, or possibly after a password change. Sending then stops until the owner re-consents. This is visible in the run record and a web banner, not by email.
- Negative: the owner sees an "unverified app" screen once during consent. That is expected for a personal-use app.
- Negative: it is tied to Gmail. Another email provider needs a new ADR.
- Follow-ups:
  - **#22:** the OAuth client (manual step), the `gmail-sender` secret, the consent step in the runbook, `Mailer` with `FakeMailer` and tests.
  - **#30:** summary email content (UC-09).
  - **#27:** blocked-run alert (UC-08).
  - **#33:** budget and failure alerts.
  - On acceptance: architecture Q8; ADR-0006's "email key" now means the `gmail-sender` secret.
