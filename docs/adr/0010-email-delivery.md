# ADR-0010: Email delivery

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #21 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

Job Finder sends a few emails, all to one recipient, the owner:

- **Summary** after a run with at least one package (UC-09). Sent at most 10 minutes after the run ends (NFR-R4).
- **Alerts** (NFR-O2):
  - a blocked run (UC-08);
  - a failed run;
  - the LLM budget alert: $5 of the $10 cap, from the app's cost ledger;
  - a restriction notice.

The hosting budget alert (NFR-C1) is sent by Cloud Billing itself, not by Job Finder. A run that crashed is marked failed by the next worker execution (ADR-0007), which then sends the alert.

Volume is a few emails a week. Email *applications* are out of the MVP (#4).

**The owner's requirement: sending is a system function, not tied to any user.** Signing in as `user@gmail.com` with the same address in the profile must not mean the mail is sent through that account. The sender belongs to the application; the recipient comes from the user's settings.

Other inputs:

- **Domain.** The owner has a domain in Cloudflare (DNS on Cloudflare). It is the zone that also publishes A-1 through Cloudflare Tunnel. The application itself stays on `*.run.app` (ADR-0006).
- **Sender process.** The worker on Cloud Run sends, with secrets from Secret Manager (NFR-S2).
- **Content.** No resume content in emails (NFR-P6).
- **Cost.** Hosting ≤ $5/month (NFR-C1).

## Decision drivers

- A system sender, independent of the signed-in user and of the owner's personal mailbox.
- Lands in the inbox: the sender's own domain, signed with SPF and DKIM, with DMARC aligned.
- The credential the worker holds can only send, and only from our domain.
- Free; few moving parts; testable without sending real mail (NFR-M5).

## Options considered

### Option 1: Cloudflare Email Service (Email Sending) on the owner's domain

The domain is onboarded under Compute → Email Service → Email Sending. Cloudflare adds DNS records on a `cf-bounce` subdomain: MX for bounces, SPF and DKIM. It also adds a DMARC record at `_dmarc.<domain>`. The domain's own MX records are not changed. The worker sends with the REST API (`POST …/accounts/{account_id}/email/sending/send` with a bearer API token); SMTP is also available.

- Good: a real system sender, e.g. `jobfinder@<domain>`, with the domain's own DKIM; DMARC aligns. Delivery to Gmail is the expected path, not a workaround.
- Good: sending to **verified destination addresses** of the account is free on Free and Paid plans. We send only to the owner's address, which is verified once.
- Good: a narrow credential — an API token with only the *Email Sending: Edit* permission, scoped to the account.
- Good: HTTPS from Cloud Run, no SMTP ports.
- Bad: Email Sending is in **beta**. Sending to any recipient that is not a verified destination needs the paid Workers plan.
- Bad: a DMARC record is added at the domain apex. If the domain already has one, it is merged during onboarding.

### Option 2: A dedicated Gmail account through the Gmail API (`gmail.send`)

- Good: free, no domain needed, send-only scope.
- Bad: one more account to keep alive (2-step verification, recovery, occasional sign-ins).
- Bad: a refresh token that a password change or security event revokes; an OAuth client with an "unverified app" consent.
- Bad: mail from a new Gmail address may start in spam. Kept as the **fallback** if Cloudflare Email Sending is unavailable.

### Option 3: A dedicated Gmail account over SMTP with an app password

- Bad: the app password gives full access to that account (Google calls app passwords "not recommended"), and they may be phased out. Rejected.

### Option 4: A transactional email service on its free tier (Brevo, Resend, Mailjet, SMTP2GO)

- Good: free tiers far above our volume (e.g. Brevo 300/day, Resend 100/day).
- Bad: still needs our domain (the same DNS work as Option 1), plus a second provider, account and API key.
- Kept as the path if the product ever emails many recipients (Option 1 would then need a paid plan).

### Option 5: The owner's own Gmail (the previous draft)

- Rejected by the owner: it ties sending to a user's mailbox.

## Decision

**Option 1: Cloudflare Email Sending from a system address on the owner's domain, sent by the worker through the REST API. Fallback: Option 2.**

1. **Domain and sender (manual, once — runbook in #22):**
   - onboard the domain in Email Sending; check that the `cf-bounce` and `_dmarc` records are active;
   - the sender is `jobfinder@<domain>`, name "Job Finder", with no mailbox behind it. Replies are not expected; the message says so;
   - add the owner's notification address as a **verified destination address** in Cloudflare; the owner confirms it from the verification email.
2. **Credential:**
   - a Cloudflare API token with only **Email Sending: Edit**, scoped to the one account, with no other permissions. It is stored in the secret `email-sender` as JSON: account id, token, sender address;
   - this is the "email key" of ADR-0006 and ADR-0009, so the project still has 5 secrets;
   - only the `worker` service account can read it; the owner adds the value (ADR-0009). Rotation every 90 days (NFR-S5).
   - The domain name stays out of the public repo: it is the A-1 zone, so it lives only in this secret and in Cloudflare.
3. **Recipient:**
   - "To" is the notification email from `settings/owner` (UC-02), by default the sign-in address (UC-01);
   - each message has exactly one recipient, with no Cc or Bcc, and no code path sends to anyone else (tested);
   - Cloudflare itself accepts only verified destinations on the free plan, a second guard. Changing the notification email in UC-02 therefore also requires verifying the new address in Cloudflare; the settings page says so.
4. **Content:**
   - **Summary:** profile name, run date, counts, and for each package its title, company, channel and a link to the package page;
   - **Alert:** the reason and a link to the run;
   - **never:** resume text, answers, cover notes or dossier facts (NFR-P6);
   - plain text plus simple HTML, no external images or tracking; the subject starts with `[Job Finder]`;
   - **untrusted input:** titles and company names come from job boards. CR and LF are removed from the subject; the HTML body is escaped by the template engine (autoescape); the JSON payload is built with a serializer, not by string concatenation. Tests include a title with `\r\nBcc:` and HTML markup.
5. **Code.** `jobfinder.notify` has an interface `Mailer` with three implementations:
   - `CloudflareMailer`, the REST API with `httpx`;
   - `GmailApiMailer`, the fallback, added only if needed;
   - `FakeMailer`, for tests.

   Sending comes after the packages are stored (NFR-R5, ADR-0007 write order). A failed send is retried twice with backoff, and the result is recorded on the run.
6. **When sending fails** (token revoked, domain removed, Cloudflare unavailable):
   - the run record gets `email: failed (<error class>)`; neither it nor the logs contain the address, the token or the body (NFR-P6);
   - the web app shows a banner "Email delivery is not working"; the run still counts as completed;
   - the runbook covers checking the token, the destination verification and the DNS records.

**Deliverability (the issue's SPF/DKIM question).** The domain is onboarded in Cloudflare, so SPF and DKIM are published and DMARC aligns for `jobfinder@<domain>`. The owner may add a Gmail filter "never send to spam" for the sender once, as extra insurance.

**Cost.** Free: sending only to the verified owner address; Cloudflare DNS is already in use.

Out of scope: email *applications* (#32); other recipients; receiving mail; push or chat notifications.

## Consequences

- Positive: a system sender that belongs to the application, on its own domain with proper authentication; the user's mailbox is not involved.
- Positive: a narrow, account-scoped token that can only send; free at our volume.
- Positive: the domain is already in Cloudflare, so there is no new provider.
- Negative: Email Sending is in beta; behaviour or pricing may change. The `Mailer` interface keeps the switch to Option 2 or 4 a small change.
- Negative: on the free plan only verified addresses receive mail; a new notification address needs verification in Cloudflare. That matches a single-user MVP. Many recipients would need a paid plan or Option 4.
- Negative: a few manual DNS and dashboard steps on the owner's Cloudflare account.
- Follow-ups:
  - **#22:** the onboarding steps in the runbook; the `email-sender` secret; `Mailer` with `CloudflareMailer` and `FakeMailer` and their tests.
  - **#30:** summary content (UC-09). **#27:** blocked-run alert (UC-08). **#33:** budget and failure alerts.
  - **UC-02:** a changed notification email must be verified in Cloudflare (noted in UC-02).
  - **On acceptance:** CLAUDE.md index.
