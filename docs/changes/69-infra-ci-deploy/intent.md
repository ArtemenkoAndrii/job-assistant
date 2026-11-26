# Intent: Infrastructure and CI deploy (skeleton 1/3)

| | |
|---|---|
| **Issue** | #69 (slice 1 of the walking skeleton, epic #22) |
| **Author** | ArtemenkoAndrii (owner); drafted by Claude |
| **Status** | Accepted |
| **Date** | 2026-11-26 |

## Problem

The architecture and ADR-0006 to ADR-0009 describe where the product runs and how it is deployed, but nothing exists yet: no GCP project setup, no Terraform, no deploy workflow, no runbook. Until a build of the app reaches Cloud Run from `main` without keys, none of the ADRs is proven, and the next skeleton slices (login, A-1 snapshot) have nowhere to deploy.

## Proposed outcome

- The owner follows a runbook once (project, billing, Firebase, platform apply, secrets, GitHub variables), and the platform layer is applied from Cloud Shell.
- After that, a merge to `main` that changes the app builds the image and CI applies the app layer through WIF, with no keys and no secrets in GitHub. `app-plan.yml` plans the app layer on PRs, and the weekly `drift.yml` checks it for drift.
- The deployed `jobfinder-web` answers `/healthz`. The service is behind IAP from the first deploy, like the whole service (ADR-0008); the IAP OAuth client is a runbook step before it. The app-side JWT check comes in #70. `deploy.yml` does not call `/healthz` over the network: it waits until the new revision is Ready (Cloud Run's startup probe on `/healthz`). The owner opens `/healthz` through IAP by hand.
- The platform layer creates everything ADR-0009 lists now (Firestore, files bucket, secret containers, IAM, WIF, budget). Secret values are added when a slice needs them.
- Cold start after scale to zero and the image size are measured from Cloud Run metrics and request logs and recorded, so NFR-A1 (cold start ≤ 10 s) and the hosting budget are checked against reality, not estimates.

## Affected users and systems

- Users: the owner, who bootstraps and operates the deployment. No end-user screen changes.
- Systems: GCP project `job-finder`, `infra/platform`, `infra/app`, GitHub Actions workflows, Artifact Registry, Cloud Run service and job, Cloud Scheduler, WIF, IAP, Firestore, the files bucket, Secret Manager, `apps/jobfinder` (minimal `/healthz` and entry points only).
- Use cases: none directly; this is the foundation for all of them.

## Constraints

- Accepted ADRs: 0005 (one image), 0006 (hosting), 0007 (storage resources), 0008 (IAP), 0009 (two Terraform layers, WIF, runbook).
- NFR-A1 (cold start), NFR-C1 (hosting ≤ $5/month with budget alerts), NFR-S2 to NFR-S4 (secrets, HTTPS, least privilege), NFR-M3 (infrastructure as code).
- The repo is public: no secrets, project number or owner email in the diff.
- PR checks (`ci.yml`) never touch the cloud, A-1 or job boards; Terraform is validated there without a backend. Only `app-plan.yml` (read-only) and `deploy.yml` (on `main`) reach GCP, through WIF.

## Out of scope

- Login and the owner check in the app (slice 2), the A-1 snapshot call (slice 3).
- Real worker logic, data model beyond what the infrastructure needs, notifications.
- Monitoring beyond the budget alert (#33); a second environment.
