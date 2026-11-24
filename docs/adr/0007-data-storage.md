# ADR-0007: Data and file storage

| | |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-11-24 |
| **Issue** | #18 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

[ADR-0006](0006-hosting.md) puts Job Finder in its own GCP project `job-finder` (`us-central1`) on the owner's billing account; the web app and the worker run on Cloud Run. The [architecture](../architecture.md) §5 lists the data: account and settings, profiles with two uploaded files each, runs, vacancies, dossiers, packages (with a generated resume PDF), the applied registry, the cost ledger and page-load counters. ADR-0006 also needs a **run queue with a lease**, so that one worker executes runs at a time (NFR-R2).

Volume is tiny: one user, ≤ 3 profiles, ≤ 25 vacancies and ≤ 8 employers per run, a few runs a week.

Requirements:
- Store only what is needed (NFR-P1).
- Retention: 90 days for packages and dossiers not applied to; the applied registry until deleted; run records 12 months; logs 30 days (NFR-P3).
- Deleting a profile removes its data within 24 h; backups expire within 7 days (NFR-P4).
- Daily backups kept 7 days (NFR-A6).
- Uploads ≤ 5 MB (NFR-F2).
- Packages are stored before the summary email (NFR-R5).
- Hosting ≤ $5/month in total (NFR-C1).

**Owner input:**
- The owner already uses Firestore (Native mode, Standard edition) in another project and prefers it.
- The project is linked to Firebase, so the owner can browse the data in the Firebase console.
- The original uploaded files are kept, not only the extracted text.

## Decision drivers

- Cost: free tier or cents (NFR-C1).
- Retention and deletion can be enforced by the platform, not only by our code (NFR-P3, P4).
- Little to operate: managed, backed up, no server.
- Works from Cloud Run with service-account identities; testable offline (NFR-M5).
- The owner's familiarity.

## Options considered

### Database

**D1. Firestore (Native mode, Standard edition) in the `job-finder` project.**
- Good: serverless, no instance to pay for. The first database in a project gets the free tier: 1 GiB stored, 50,000 reads, 20,000 writes and 20,000 deletes a day. Our volume is a tiny fraction of that.
- Good: TTL policies delete expired documents automatically; scheduled backups; transactions for the run lease; IAM per service account. The owner knows it.
- Bad: a document database — queries need planned indexes, no joins; TTL deletes, PITR, backups and restores are billed outside the free tier (cents at our size).

**D2. Cloud SQL (PostgreSQL).**
- Good: relational, SQL, mature tooling.
- Bad: an always-on instance even at the smallest size; that alone would use most or all of the $5 budget. Rejected.

**D3. SQLite file on Cloud Storage (or a mounted bucket).**
- Good: free, simple, SQL.
- Bad: the web app and the worker write at the same time from different instances; a file on object storage has no safe locking. Rejected.

**D4. A collection in the existing `mas-home` database.**
- Bad: shares IAM with another project's services (resumes readable by them) and uses that project's free tier. Rejected in ADR-0006.

### Files

**F1. Cloud Storage bucket in `us-central1`** (5 GiB storage and 55,000 operations a month free) vs **F2. files inside Firestore documents** (1 MiB document limit; PDFs and 5 MB uploads do not fit). F1.

## Decision

**D1 + F1: Firestore (Native, Standard) and one private Cloud Storage bucket, both in the `job-finder` project, `us-central1`.** The project is linked to Firebase for console access by the owner only; no Firebase client SDK or security rules are used — the app accesses data only from the server with service accounts.

**Firestore collections** (one document per entity; IDs are random unless noted):

| Collection | Holds | Personal data | Retention |
|---|---|---|---|
| `settings/owner` | notification email, re-apply period, kill switch, paused job boards | email | until deleted |
| `profiles` | name, active, schedule, file paths, extracted fields, tailoring notes | **resume content** | until the profile is deleted |
| `runs` | profile, trigger, status (`queued`, `running`, `completed`, `blocked`, `stopped`, `failed`), counts, cost per step, duration, errors | — | 12 months (`expire_at`) |
| `runs/{id}/vacancies` | source, job id, link, company, title, normalised match key, status, skip reason | — | with the run |
| `dossiers` | company, facts with source links, missing sources | — | 90 days (`expire_at`), cleared when applied |
| `packages` | vacancy, PDF path, added skills (+ rejected), answers, cover note, reviewer notes, channel | **resume content** | 90 days (`expire_at`), cleared when applied |
| `applied` | position, company, source, link, channel, profile, date, package; match keys (source + job id, normalised company + title, UC-15) | links to the package | until the owner deletes it |
| `cost_ledger/{yyyy-mm}`, `page_loads/{board}-{date}` | LLM cost per month and step; page loads per board per day | — | 12 months |
| `locks/worker` | the run lease: holder (job execution id), `expires_at` | — | — |

**Retention (NFR-P3):** a TTL policy on the field `expire_at`. Marking a vacancy *applied* clears `expire_at` on its package and dossier, so they live as long as the registry entry. Firestore deletes expired documents in the background, not at the exact moment; that is fine for retention. Where a deadline matters (profile deletion, NFR-P4) the app deletes explicitly instead of relying on TTL.

**Files:** bucket `job-finder-files-<suffix>`, uniform bucket-level access, public access prevention on, no public or signed links (downloads go through the web app after sign-in).

| Path | Holds | Retention |
|---|---|---|
| `profiles/{profile_id}/resume.*`, `.../requirements.*` | original uploads (≤ 5 MB, .pdf/.txt/.md) | until the profile is deleted |
| `packages/{package_id}/resume.pdf` | tailored resume | lifecycle rule: delete after 90 days, except objects with the `applied=true` metadata flag, which the app sets on *applied* |

Soft delete stays at the default 7 days (recovers mistakes; matches the 7-day backup expiry in NFR-P4).

**Deletion (NFR-P4):** deleting a profile deletes, in one request, its documents (profile, runs with vacancies, packages, dossiers used only by it), and its files; applied-registry entries of that profile are deleted too, after a confirmation in the UI. Backups and soft-deleted objects expire within 7 days.

**Backups (NFR-A6):** a daily Firestore scheduled backup kept 7 days. A restore drill once before the MVP release (NFR-A6).

**Run queue and lease (ADR-0006):** "Run now" and the hourly tick create `runs` documents with status `queued`. A worker execution takes the lease in a Firestore transaction (`locks/worker` free or expired → set holder and `expires_at` = now + 10 min), renews it every few minutes during the run, and releases it at the end. If a worker crashes, the lease expires and the next execution takes over. A second execution that finds a valid lease exits at once.

**Access (NFR-S4):** service accounts `web` and `worker` get `roles/datastore.user` on the project and `roles/storage.objectUser` on the bucket only; `deployer` gets no data access. The owner reads data in the Firebase console with their own account.

**Code:** `jobfinder.storage` defines repository interfaces used by the pipeline and the web app; the Firestore implementation uses the official async client (`google-cloud-firestore`) and `google-cloud-storage`. Unit tests use in-memory fakes of the repositories; an emulator-based integration test is added in #22 if needed. No code outside `storage/` imports a Google client.

**Expected cost:**

| Item | Usage per month | Cost |
|---|---|---|
| Firestore reads, writes, storage | thousands of operations, < 50 MB | free tier |
| TTL deletes | a few hundred documents | < $0.01 |
| Daily backups, 7 kept | < 50 MB each | ≈ $0.01–0.05 |
| Cloud Storage | < 1 GB, a few thousand operations | free tier |
| **Storage total** | | **≈ $0–0.10** |

Together with ADR-0006, hosting and storage stay **well under $1/month** at the default load.

Out of scope: sign-in and the owner's account record (#17); infrastructure code for the database, bucket, TTL policy, backup schedule and lifecycle rule (#16); test fixtures and recorded pages (#24).

## Consequences

- Positive: no database server; retention and backups are platform features; the cost is close to zero.
- Positive: data and files live in their own project with access limited to two service accounts; the owner can inspect data in a familiar console.
- Positive: the run lease is a single transactional document, no extra queue service.
- Negative: document model — every query the UI needs (runs per profile by date, vacancies per run, registry lookups by match key) needs a planned index; changes to the model need care because there are no migrations.
- Negative: TTL deletion is eventual; where deletion time matters (profile deletion), the app deletes explicitly.
- Negative: tests need fakes or the Firestore emulator; the dev container has no cloud credentials by design (ADR-0002).
- Follow-ups:
  - #16: Terraform for the Firestore database, TTL policy, backup schedule, bucket with lifecycle rule and soft delete, IAM bindings; Firebase link.
  - #22: repositories for `settings`, `runs` and the lease; deploy; restore drill before release.
  - #17: where the owner's identity and session live.
  - Update [architecture](../architecture.md) Q5 and §5 on acceptance.
