# ADR-0006: Hosting

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-24 |
| **Issue** | #15 |
| **Deciders** | ArtemenkoAndrii (owner); drafted with Claude |

## Context

The [architecture](../architecture.md) has a web app, a scheduler, a run queue with one run at a time, a run worker that runs for 30–90 minutes, a database, file storage and a secret manager. [ADR-0005](0005-application-stack.md) packs the web app and the worker into **one container image** with two entry points.

Constraints and inputs:

- Hosting ≤ **$5/month**, with budget alerts (NFR-C1). The LLM budget is separate.
- The web app may scale to zero; a cold start of ≤ 10 s is acceptable (NFR-A1).
- One run at a time (NFR-R2); a run takes ≤ 90 min (NFR-R3); the default schedule is weekly and can be changed per profile (NFR-R1).
- HTTPS everywhere (NFR-S3); least-privilege service accounts, no long-lived keys (NFR-S4); secrets only in a secret manager (NFR-S2).
- Vision §10: GCP is preferred; the owner has a GCP account with billing. Any region is allowed (NFR-P2), and the owner accepts a US region for the larger free tier. No custom domain for now.
- The worker must reach A-1 (Cloudflare Access over the internet), OpenAI and the email service.
- The owner's billing account already runs another project ("Mas Home") in `us-central1`: two Cloud Run services and a Firestore database (Native mode, Standard edition). The owner prefers to reuse Firestore if it fits (#18).

Database and file storage are decided in #18, sign-in in #17, Terraform and CI deployment in #16, email in #21.

## Decision drivers

- Monthly cost at the expected load, ideally within the free tier.
- Long runs: a job of up to 90 minutes must not be cut off.
- Little to operate: no OS patching, no servers to keep alive.
- Fits one image with two entry points; managed HTTPS; managed identities for least privilege.

## Options considered

### Option 1: GCP Cloud Run — service for the web app, job for the worker

The web app runs as a Cloud Run **service**; the worker as a Cloud Run **job**, started by Cloud Scheduler and by "Run now".

- Good: Cloud Run's free tier covers 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests a month for request-billed services. Jobs have their own allowance: 240,000 vCPU-seconds and 450,000 GiB-seconds per month (us-central1 pricing).
- Good: a job task can run up to 168 hours (7 days). The default timeout is 10 minutes, so it must be set.
- Good: scale to zero, managed HTTPS on `*.run.app`, a service account per workload, and deployment from CI without keys (#16).
- Good: Cloud Scheduler gives 3 free jobs per billing account, and Secret Manager's free tier covers 6 secret versions.
- Bad: cold starts on the web app. Startup CPU boost doubles the CPU during startup and for 10 seconds after.
- Bad: a GCP-specific deployment, although the image itself stays portable.

### Option 2: one always-on VM (GCP e2-micro free tier, or a €4/month VPS)

- Good: one machine for everything; no cold starts; cron and a long-running process are trivial.
- Bad: we patch the OS, run TLS, manage a process supervisor and back up the disk ourselves. A small VM is tight for Python + WeasyPrint + the worker. Secrets and identities are manual. More to operate for one part-time developer.

### Option 3: PaaS (Fly.io, Render, Railway)

- Good: simple deploys from an image.
- Bad: no lasting free tier for an always-available web app plus a 90-minute worker; around $5–7 a month before storage; a second provider next to the preferred GCP.

### Option 4: Cloud Run functions for the worker

- Bad: HTTP functions are capped well below 90 minutes; a function is the wrong shape for a long batch run. Rejected.

## Decision

**Option 1: GCP, region `us-central1`, Cloud Run service + Cloud Run job, in a new GCP project `job-finder` on the existing billing account.**

Why a separate project rather than the existing "Mas Home" project: Job Finder stores resumes, so its data and secrets must not be readable by the other project's service accounts; a project is GCP's main IAM, quota and billing-report boundary, and deleting the product later is one action. The billing account and the region stay the same. Reusing Firestore is decided in #18; Firestore in the new project is the leaning there, since the owner already uses it.

| Component | Service | Configuration |
|---|---|---|
| Web app | Cloud Run **service** `jobfinder-web` | Image entry point `uvicorn`; request-based billing; min instances 0, max 2; 1 vCPU, 512 MiB (raised if PDF regeneration with WeasyPrint needs more, measured in #22); startup CPU boost on; public HTTPS on `*.run.app`, the app itself requires sign-in (#17) |
| Run worker | Cloud Run **job** `jobfinder-worker` | Entry point `python -m jobfinder.worker`; 1 task, parallelism 1; 1 vCPU, 1 GiB; task timeout **2 h**; **max retries 0** (a blocked run is not retried, NFR-A2) |
| Scheduler | Cloud Scheduler, **one** job | Every hour at minute 30 (so the default Sat 01:30 slot is exact), starts `jobfinder-worker`. The worker reads which profiles are due (per-profile schedule, NFR-R1) and exits in seconds if none are. A blocked or failed run does not make a profile due again: it waits for its next scheduled slot (NFR-A2, no retry loop) |
| Run queue | rows in the database (#18) | "Run now" adds a queued run and starts a job execution through the Cloud Run Admin API. A lease in the database ensures only one worker executes runs (NFR-R2); a second execution finds the lease taken and exits |
| Secrets | Secret Manager | A-1 client id and secret, OpenAI key, email key, session key — 5 secrets. Rotation (NFR-S5) destroys the old version, so the free 6 active versions are not exceeded (#16) |
| Images | Artifact Registry, `us-central1` | Cleanup policy: keep the last 3 images |
| Logs and metrics | Cloud Logging and Monitoring | 30-day retention (NFR-P3) |
| Cost control | Cloud Billing budget **$5/month** | Alerts at 50%, 90% and 100% to the owner (NFR-C1) |

**Identities (least privilege, NFR-S4):**

| Service account | Can |
|---|---|
| `web` | Read the OpenAI and session secrets; start the worker job (only that job); data access per #18 |
| `worker` | Read the A-1, OpenAI and email secrets; data access per #18 |
| `scheduler` | Start the worker job |
| `deployer` (CI, #16) | Deploy the service and the job; push images; no data access |

The A-1 token is readable only by `worker` (architecture §2).

**Expected cost, one profile, weekly runs:**

| Item | Usage per month | Cost |
|---|---|---|
| Worker job | 4 runs × ≤ 90 min ≈ 21,600 vCPU-s + 720 hourly checks × ~10 s ≈ 7,200 vCPU-s | within the jobs free tier (~12% of it) |
| Web service | a few hundred requests, a few thousand vCPU-s | within the free tier |
| Cloud Scheduler | 1 job | free (3 per billing account) |
| Secret Manager | 5 secrets, a few thousand accesses | free (6 versions) |
| Artifact Registry | 3 images × ~150–250 MB | ~$0–0.05 above the 0.5 GB free |
| Egress | page snapshots and LLM traffic, well under 1 GiB | free (1 GiB within North America) |
| **Hosting before storage (#18)** | | **≈ $0–0.10** |

The Cloud Run and Cloud Scheduler free tiers are **per billing account**, so the existing "Mas Home" services use part of the same allowance. Their usage is checked in the billing report before deployment (#22); the $5 budget is scoped to the `job-finder` project, so it measures Job Finder alone.

The worst case in the NFRs — 3 profiles daily, every run the full 90 minutes — is ~490,000 vCPU-s, about **$4.6/month** above the free tier: under the cap, but it would leave almost nothing for storage (#18). The worker mostly waits on the network (pauses, A-1, LLM), so 0.5 vCPU would bring the same load to ~$0.1/month; below 1 vCPU Cloud Run allows at most 512 MiB, so this is measured in #22 before it is changed.

**Infra vs LLM** (LLM from spike #3 and NFR-C5: ~$0.15–0.25 per run incl. web search; hosting from the table above, storage #18 not included):

| Load | Runs / month | Hosting | LLM | Within caps? |
|---|---|---|---|---|
| 1 profile weekly (default) | ~4.3 | ≈ $0–0.10 | ≈ $0.65–1.10 | Yes: hosting ≤ $5, LLM ≤ $10 |
| 1 profile daily | ~30 | ≈ $0–0.10 | ≈ $4.50–7.50 | Yes; LLM alert at $5 may fire |
| 3 profiles daily, full 90 min (worst case) | ~90 | ≈ $4.6 | ≈ $13.50–22.50 | **No — the LLM cap is reached first**; the budget guard stops runs (*stopped: budget*, NFR-C4) |

The LLM budget, not hosting, is what limits how often runs can happen.

Out of scope: database and file storage (#18), sign-in (#17), Terraform layout and CI deployment (#16), email (#21), a custom domain.

## Consequences

- Positive: nothing to patch or keep alive; HTTPS, identities, logs and scale-to-zero come with the platform; expected hosting cost is close to $0.
- Positive: the 90-minute run is a first-class job with its own timeout and no retries; the web app stays small and fast.
- Positive: the image stays portable — another container platform needs only new deployment code.
- Negative: cold starts of the web app after idle; measured in #22 against NFR-A1 (startup CPU boost on; lazy imports of heavy libraries such as WeasyPrint).
- Negative: the hourly worker tick costs a little compute for nothing most of the time; cheaper than a scheduler job per profile and simpler than updating schedules in Cloud Scheduler.
- Negative: data of an EU resident is stored in the US; accepted by the owner for the MVP (NFR-P2), revisit if the product gets other users.
- Follow-ups:
  - #16: Terraform for all of the above, CI deployment through Workload Identity Federation, budget alerts.
  - #18: database and file storage in `us-central1`, the run queue table and the lease.
  - #17: sign-in on `*.run.app`.
  - #22: deploy the skeleton; measure cold start and image size; confirm the job timeout and the Admin API trigger.
