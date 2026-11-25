# ADR-0010: Notifications and email delivery

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-25 |
| **Issue** | #21 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

Job Finder notifies its user about a few events:

| Event | Source | Requirement |
|---|---|---|
| Run summary, when a run produced at least one package | worker | UC-09; sent ≤ 10 min after the run (NFR-R4), after the packages are stored (NFR-R5) |
| Run blocked (session expired, challenge, A-1 down) | worker | UC-08, NFR-O2 |
| Run failed | worker; a crashed run is marked failed by the next worker execution (ADR-0007) | NFR-O2 |
| LLM budget alert ($5 of the $10 cap) | worker, from the cost ledger | NFR-C2, NFR-O2 |
| Restriction notice from a job board | worker | UC-08 A1, NFR-O2 |

The hosting budget alert (NFR-C1) is sent by Cloud Billing itself.

Volume: a few notifications a week, one recipient. In the MVP the only channel is email (UC-09). Email *applications* are out of the MVP (#4).

**Owner requirements:**
1. **Sending is a system function, not tied to any user.** Signing in with a Gmail address that is also in the profile must not mean mail is sent through that account. The sender belongs to the application; the recipient comes from the user's settings.
2. **Notifications sit behind an interface.** Email is one channel. Another channel (e.g. Telegram) can be added, or email replaced, without touching the pipeline.
3. **No beta services**, and **no restriction to pre-verified recipients**. This rules out Cloudflare Email Sending.

Other inputs:
- The application is on `*.run.app` with no domain of its own (ADR-0006).
- The worker sends, with secrets from Secret Manager (NFR-S2).
- No resume content in notifications (NFR-P6).
- Free (NFR-C1).

## Decision drivers

- A system sender, independent of any user's mailbox.
- Reaches the inbox without a domain of our own.
- The credential the worker holds can only send.
- No expiring tokens to renew on a schedule; no app verification process.
- Channels are pluggable; pipeline code knows events, not channels.
- Free; testable without sending anything (NFR-M5).

## Options considered

### Email transport

**E1. A dedicated Gmail account, Gmail API with scope `gmail.send`, OAuth client in Personal mode.**

*Personal mode* is a Google Auth Platform user type for applications built solely for the creator's own use:
- Only the Google Account that created the application can authorise it.
- It is not subject to the 7-day test-user token expiration, nor to the OAuth user cap.
- It needs no OAuth branding or scope verification.
- The type is chosen once: it cannot be switched to External or Internal later.

The dedicated account creates the application, so the dedicated account itself grants `gmail.send`.

- Good: a system sender; mail is signed by Google for `gmail.com`, so SPF, DKIM and DMARC align without a domain; any recipient.
- Good: `gmail.send` can only send; it cannot read or change the mailbox. No 7-day expiry, no verification, free.
- Bad: one more Google account to keep alive (2-step verification, recovery, an occasional sign-in).
- Bad: a password change of that account revokes refresh tokens with Gmail scopes, so it needs a re-consent.
- Bad: mail from a new address may first land in spam until the recipient marks it.

**E2. The same dedicated Gmail account over SMTP with an app password.**
- Good: no OAuth.
- Bad: an app password grants full access to the account, and Google does not recommend app passwords. Kept as a fallback only.

**E3. Cloudflare Email Sending on the owner's domain.**
- Bad: beta; free only to pre-verified recipients. Rejected by the owner.

**E4. A transactional email service** (Brevo, Resend, Mailjet, …).
- Bad: needs a sending domain with SPF and DKIM to avoid spam; another provider and API key. Revisit if the product gets its own domain or many users.

**E5. The signed-in user's own Gmail** (an earlier draft).
- Bad: ties sending to a user. Rejected by the owner.

### Notification structure

**N1. Pipeline calls a mailer directly.**
- Bad: every new channel touches the pipeline.

**N2. A notification service with channels.**
- The pipeline emits typed events.
- A `Notifier` renders and delivers them to each enabled channel.
- A channel is one class.

## Decision

**E1 + N2.** A dedicated Gmail account sends through the Gmail API (`gmail.send`), with its OAuth client in Personal mode. Email is a channel behind a notification interface.

### Notification design (`jobfinder.notify`)

```
pipeline / worker ──► Notifier.notify(event) ──► for each enabled channel:
                                                    channel.send(event, recipient)
events:   RunSummary, RunBlocked, RunFailed, BudgetAlert, RestrictionNotice
channels: EmailChannel (Gmail API)        — MVP
          TelegramChannel, …              — later, one class each
          FakeChannel                     — tests
```

**Events.**
- Typed models with only what a message may show: profile name, run id and date, counts; for a summary, title, company, channel and link per package; for an alert, the reason and a link.
- Never resume text, answers, cover notes or dossier facts (NFR-P6).
- The pipeline only creates events; it knows nothing about channels.

**Channels.**
- Each implements `NotificationChannel`: `name`, `send(event, recipient) -> DeliveryResult`.
- Each renders its own format from shared templates (email: plain text + HTML; Telegram later: short text).
- Channels and recipients come from settings and configuration: the MVP has one channel, `email`, sending to the notification email (UC-02).

**Delivery.**
- `Notifier` calls every enabled channel independently; a failing channel does not stop the others.
- Each channel retries twice with backoff (30 s, 2 min — at most ~3 min, within NFR-R4).
- The result per channel is recorded on the run.
- If the worker crashes between "run completed" and a recorded delivery, the next worker execution re-sends summaries for completed runs with no delivery record that ended less than a day ago.

**Failure visibility.**
- A channel that keeps failing sets `delivery: failed (<channel>, <error class>)` on the run and a banner in the web app ("Notifications are not being delivered").
- Records and logs never contain the recipient, the token or the message body (NFR-P6).

**Untrusted input.**
- Titles and company names come from job boards.
- The email channel builds messages with `email.message.EmailMessage`, removes CR and LF from header values (so a title cannot inject `Bcc:`), and autoescapes HTML.
- Every channel has exactly one recipient per message.
- Tests use a title containing `\r\nBcc:` and HTML markup.

### Email channel

1. **Sender account (manual, once — runbook in #22).**
   - The owner creates a new personal Gmail account for Job Finder, with 2-step verification and recovery options.
   - The address is a configuration value in the secret, not in the repo.
2. **Personal mode application (manual, once).** Signed in as the sender account, the owner:
   - creates a small Google Cloud project owned by that account;
   - enables the Gmail API;
   - goes through the Personal mode onboarding (user type **Personal**, application type *Web application* with the OAuth Playground redirect URI);
   - grants `https://www.googleapis.com/auth/gmail.send` once, in the OAuth Playground with that client, which returns a refresh token.

   The project needs no billing and holds nothing else. It is deliberately separate from `job-finder`, whose user type is External because of IAP (ADR-0008). User types cannot be mixed or switched, and this keeps the mail credential apart from the application's cloud. Its few manual settings are the one part of the system outside Terraform (an exception to NFR-M3, recorded here and in the runbook).
3. **Secret.**
   - The secret `email-sender` in `job-finder` holds JSON: client id, client secret, refresh token, sender address.
   - It is the "email key" of ADR-0006 and ADR-0009 (still 5 secrets).
   - Only `worker` can read it.
   - The owner adds the value with `gcloud secrets versions add` (ADR-0009); it never passes through the repo, CI or the dev container.
4. **Sending.**
   - `EmailChannel` exchanges the refresh token for a short-lived access token and calls `users.messages.send` over HTTPS.
   - Nothing is written to disk.
   - "From" is the sender account; "To" is the notification email; the subject starts with `[Job Finder]`.
5. **Rotation (NFR-S5).**
   - The client secret is rotated with the other keys every 90 days.
   - The refresh token is replaced by re-consent on suspicion or after a password change of the sender account.
6. **Deliverability (SPF/DKIM).** Gmail signs mail from `gmail.com` addresses; SPF, DKIM and DMARC align without a domain of ours. The owner marks the first message "not spam" or adds the sender to contacts once.

Out of scope:
- other channels (Telegram etc.): added later as one `NotificationChannel` each, with their own ADR only if they bring a new provider or secret;
- email *applications* (#32);
- a custom domain.

## Consequences

- Positive: the sender is a system account; no user's mailbox is involved, and any recipient address works.
- Positive: the credential can only send; no expiring tokens, no verification, no beta service; free.
- Positive: notifications are channel-agnostic. A Telegram channel or a replacement for email is one class plus configuration; the pipeline is unchanged.
- Negative: a dedicated Google account and a small separate project to keep (2-step verification, an occasional sign-in, re-consent after a password change). Its manual setup is outside Terraform.
- Negative: the first messages may go to spam until marked.
- Follow-ups:
  - **#22:** `jobfinder.notify` (events, `Notifier`, `NotificationChannel`, `EmailChannel`, `FakeChannel`) with tests incl. header injection and channel isolation; the `email-sender` secret; the sender-account and Personal-mode steps in the runbook; a check that a token issued at least 8 days earlier still works.
  - **#27 / #30 / #33:** emit the blocked, summary, budget and failure events.
  - **On acceptance:** CLAUDE.md index.
