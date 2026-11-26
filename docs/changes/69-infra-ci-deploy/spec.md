# Spec: Infrastructure and CI deploy (skeleton 1/3)

| | |
|---|---|
| **Issue** | #69 (epic #22) |
| **Intent** | [intent.md](intent.md) |
| **Status** | Draft |
| **Date** | 2026-11-26 |

<!-- Written with the writing-specs skill; policy skills: security-privacy, cost-guard. mobile-first-ux and resume-rules do not apply. -->

## Related ADRs

- [ADR-0005](../../adr/0005-application-stack.md): one image with two entry points; the image the pipeline builds and deploys.
- [ADR-0006](../../adr/0006-hosting.md): Cloud Run service `jobfinder-web` and job `jobfinder-worker`, one Scheduler job, Artifact Registry, $5 budget, service accounts `web`, `worker`, `scheduler`, `deployer`.
- [ADR-0007](../../adr/0007-data-storage.md): Firestore (Native, Standard) with TTL on `expire_at` and a 7-day daily backup; one private files bucket with lifecycle and 7-day soft delete.
- [ADR-0008](../../adr/0008-user-authentication.md): IAP on the service, only the IAP agent holds `run.invoker`; `/healthz` is the one route without the app's JWT check. The JWT check itself is #70.
- [ADR-0009](../../adr/0009-infrastructure-as-code.md): two Terraform layers, WIF with numeric-ID condition, identities `app-plan` and `deployer`, the four workflows, the runbook, secret containers without values.
- [ADR-0010](../../adr/0010-email-delivery.md): only its secret container (the email key) is created here.

ADR-0011 (browser policy) is not touched.

## Requirements

### Functional

The change adds no use case; it is the foundation for all of them. Requirements trace to the intent and to ADR-0009.

| ID | Requirement | Source |
|---|---|---|
| R1 | `infra/platform` creates, in project `job-finder`: the enabled APIs; the state bucket; the WIF pool `github` and provider `github-actions`; service accounts `web`, `worker`, `scheduler`, `app-plan`, `deployer` with all their roles as in ADR-0009 and ADR-0006; the owner's IAP access (project level); Firestore with TTL on `expire_at`, daily backup kept 7 days and security rules; the files bucket (uniform access, public access prevention, lifecycle, soft delete); the five Secret Manager secrets and their access bindings, **without versions**; Artifact Registry keeping the last 3 images; log retention of 30 days; the $5 budget with alerts at 50%, 90% and 100%; the Firebase link. | ADR-0006, 0007, 0009 |
| R2 | `infra/app` creates: Cloud Run service `jobfinder-web` (image by digest, IAP on, startup probe on `/healthz`, min 0 / max 2 instances, 1 vCPU, 512 MiB, startup CPU boost, `run.invoker` only for the IAP service agent); Cloud Run job `jobfinder-worker` (1 task, parallelism 1, timeout 2 h, max retries 0, 1 vCPU, 1 GiB); one Cloud Scheduler job, hourly at minute 30, starting the worker job; who may start the job (`web`, `scheduler`). No Firestore composite index is needed yet; the layer states this and adds none. | ADR-0006, 0008, 0009 |
| R3 | Workflows. `ci.yml` adds `terraform fmt -check` and `terraform validate` (no backend) for both layers. `app-plan.yml` plans the app layer on PRs that change `infra/app/**` or `apps/**`, as `app-plan`, with `-lock=false`. `deploy.yml` runs on push to `main` that changes `infra/app/**` or `apps/**`: builds and pushes the image, applies the app layer as `deployer` with the new digest, then waits until the new revision is Ready (Cloud Run's startup probe on `/healthz`); it makes no network call to `/healthz`. `drift.yml` runs weekly, plans the app layer as `app-plan` and fails on any difference. | ADR-0009 |
| R4 | `scripts/lint.sh` fails on any workflow that uses `pull_request_target`, and on any Terraform that grants a role to `allUsers` or `allAuthenticatedUsers` on the service. | ADR-0008, 0009 |
| R5 | The runbook `docs/runbooks/bootstrap.md` lists the owner's one-time steps in order: project and billing; Firebase terms; clone, apply `infra/platform` in Cloud Shell, migrate the state to the bucket and delete the local state files; create the IAP OAuth client (External, In production) and attach it with `gcloud iap settings set` **before the first `deploy.yml` run**; add secret values when a slice needs them; set the variables of the GitHub Environment `production`. It also covers the monthly platform plan and rolling back to the previous image digest. | ADR-0009 |
| R6 | `/healthz` returns only the status and the version. The existing route in `apps/jobfinder/src/jobfinder/web/app.py` is reused. The worker entry point `python -m jobfinder.worker` starts and exits 0, so the job can be created and run. | ADR-0005, 0008 |
| R7 | Cold start of `jobfinder-web` after scale to zero and the image size are measured and recorded in `plan.md` → Proof. Cold start comes from Cloud Run's `container/startup_latencies` metric and request logs; the owner opens `/healthz` through IAP by hand. | NFR-A1 |

### Non-functional

- NFR-A1: cold start ≤ 10 s (R7).
- NFR-C1: hosting ≤ $5/month; budget and alerts exist (R1).
- NFR-S1: every request passes IAP from the first deploy; the app-side check follows in #70.
- NFR-S2: secret values never in the repo, Terraform, state, images or logs (R1, R5).
- NFR-S3: HTTPS only (Cloud Run `*.run.app`).
- NFR-S4: least-privilege accounts; CI uses WIF, no keys (R1, R3).
- NFR-M3: all resources in Terraform; the platform layer is applied and drift-checked by the owner (recorded exception, ADR-0009).
- NFR-M4, NFR-M5: one command each for build and tests; CI checks never reach GCP, A-1 or job boards.
- NFR-P2: data in `us-central1`. NFR-P3: Firestore TTL, bucket lifecycle and 30-day log retention. NFR-A6: daily backup kept 7 days.

## Acceptance criteria

- **AC1** — Given a PR, when `ci.yml` runs, then `terraform fmt -check` and `terraform validate` pass for `infra/platform` and `infra/app` without a backend and without any cloud credential.
- **AC2** — Given a pull request from a fork, when workflows run, then no GCP token is issued and no step authenticates to GCP.
- **AC3** — Given a PR from a branch of this repo that changes `infra/app/**`, when `app-plan.yml` runs, then it prints a plan as `app-plan` and writes nothing to the state.
- **AC4** — Given a clean `main` after a deploy, when `drift.yml` runs, then its plan shows no difference; given a manual change to the service, then the run fails.
- **AC5** — Given a push to `main` that changes `apps/**`, when `deploy.yml` runs, then the image is pushed, the app layer is applied with its digest (not a tag), and the new `jobfinder-web` revision becomes Ready.
- **AC6** — Given a run of any workflow other than `deploy.yml`, or a `deploy.yml` run that is not a `push` on `main`, when it asks to impersonate `deployer`, then WIF refuses.
- **AC7** — Given the repository and the GitHub Environment `production`, when they are inspected, then they hold no key, token or secret; the Environment holds only non-secret variables (project ID and number, WIF provider, service account emails); `scripts/lint.sh` (gitleaks) finds nothing in the diff.
- **AC8** — Given a request to the `jobfinder-web` URL without a Google sign-in, when it arrives, then IAP answers (redirect to sign-in or 401/403) and the container is not reached; no `allUsers` or `allAuthenticatedUsers` role exists on the service.
- **AC9** — Given the owner signed in with the allowed Google account, when they open `/healthz` through IAP, then the response is 200 with the status and the version only.
- **AC10** — Given a workflow file that uses `pull_request_target`, or Terraform that binds `allUsers` to the service, when `scripts/lint.sh` runs, then it exits non-zero.
- **AC11** — Given the platform layer applied, when `terraform plan` of `infra/platform` runs in Cloud Shell, then it shows no difference, and the console shows: Firestore TTL on `expire_at`, a daily backup kept 7 days, a files bucket with public access prevention and the lifecycle rule, Artifact Registry keeping 3 images, a $5 budget with thresholds at 50%, 90% and 100%.
- **AC12** — Given the five secrets, when their versions are listed, then none has a version before the owner adds one, and no secret value appears in either Terraform state.
- **AC13** — Given the `deployer` and `app-plan` accounts, when their effective roles are listed, then neither has project IAM admin, Firestore or bucket data access, secret-value access or billing rights, and `app-plan` cannot write or lock the app state.
- **AC14** — Given the runbook followed from the top on a new project, when the owner reaches the first deploy, then the IAP OAuth client already exists (the runbook orders it before the first `deploy.yml` run).
- **AC15** — Given `jobfinder-web` scaled to zero, when the owner requests `/healthz` through IAP, then the cold start is ≤ 10 s; the measured value, the metric used and the image size are recorded in `plan.md` → Proof.
- **AC16** — Given the worker job, when it is executed once by hand, then it exits 0 and does not retry on failure (max retries 0).

## Design

```
PR (branch)  ──ci.yml──▶ fmt, validate (no cloud)
             ──app-plan.yml──▶ WIF ─▶ app-plan SA ─▶ plan -lock=false (read-only)
push to main ──deploy.yml──▶ WIF ─▶ deployer SA ─▶ build+push image ─▶ apply (digest) ─▶ wait revision Ready
weekly       ──drift.yml──▶ WIF ─▶ app-plan SA ─▶ plan, fail on difference
owner        ──Cloud Shell──▶ apply infra/platform (IAM, data, secrets, WIF, budget)
```

Layer contents, identities and roles are as in the [ADR-0009 tables](../../adr/0009-infrastructure-as-code.md); this spec does not copy them.

- **Layout:** `infra/platform/`, `infra/app/`, `infra/.terraform-version`, a committed `.terraform.lock.hcl` per layer, provider `~> 8.0`; `.github/workflows/{app-plan,deploy,drift}.yml`; `docs/runbooks/bootstrap.md`.
- **State:** `gs://<state-bucket>/platform/` (owner only) and `gs://<state-bucket>/app/` (CI accounts). The platform layer starts with local state and is migrated to the bucket; local `.terraform` and `terraform.tfstate*` are then deleted.
- **First deploy order:** platform apply → IAP OAuth client attached → GitHub Environment variables set → merge to `main` triggers `deploy.yml`. Because Artifact Registry is a platform resource, the repository exists before the first push.
- **Image:** built from `apps/jobfinder/Dockerfile`, referenced by digest. The existing smoke test in `ci.yml` stays.
- **Rollback:** re-run the app apply with the previous digest (runbook).
- **Owner email:** a variable of the platform layer only, entered in Cloud Shell. It reaches the app as the Secret Manager secret `JOBFINDER_OWNER_EMAIL` (value added by the owner, used from #70).
- **Unchanged application code:** only `/healthz` (exists) and the worker stub entry point.

## Security, privacy and cost

- **Security:** no keys anywhere: CI uses WIF with a numeric repository and owner ID condition (NFR-S4). `deployer` is bound to `deploy.yml` on `refs/heads/main` and the `push` event, so `pull_request_target`, `workflow_run`, `issue_comment` and `workflow_dispatch` cannot use it. `app-plan` has no data, secret, IAM or platform-state access and cannot lock the state. The stated boundary stays: whoever deploys the code can act as the app, and that is limited to reviewed code on `main`. Secret values are added by the owner with `gcloud` and never pass through the repo, CI or state (NFR-S2). The service is behind IAP from the first deploy; no route is public (NFR-S1). New outbound domains: CI reaches the Terraform registry and GCP APIs; the dev container gets none (see Flagged concerns 5).
- **Privacy:** no personal data is stored by this change. The owner's email is only a platform variable, kept in the platform state (a private bucket readable by the owner); it never goes to GitHub or the repo. No logs carry resume text or emails (NFR-P6); log retention is 30 days (NFR-P3). Region `us-central1` (NFR-P2).
- **Cost:** +$0 LLM per run (no LLM call). Cloud: Cloud Run service and job, Scheduler (one job, within the 3 free), Secret Manager (5 secrets, versions within the free 6 once added), Artifact Registry (3 images, within the free 0.5 GB if the image is small; the size is measured), Firestore (empty, free tier), backup (cents), bucket (free tier), budget (free), IAP (free). Expected total under $1/month, below half of NFR-C1. The hourly Scheduler tick starts a job that exits at once; it stays within the job free allowance.

## UX

Not applicable: no screen, component or email. The only response is the plain `/healthz` status.

## Flagged concerns

1. **ADR-0008 vs ADR-0009 on the owner email.** ADR-0008 says the email is a Terraform variable whose value is in a GitHub Actions secret; ADR-0009 (later) keeps it in the platform layer, never in GitHub. This spec follows ADR-0009. Proposed: fix the sentence in ADR-0008 in this PR. Owner decides.
2. **Lint rules moved earlier.** ADR-0009 assigns the `pull_request_target` rule and the `allUsers` check to #22; this spec places them in #69 (R4) because #69 adds the workflows and the service. Owner confirms.
3. **Platform drift has no CI evidence.** The platform layer is not planned by CI (ADR-0009), so AC11 is checked by the owner in Cloud Shell and recorded by hand. Accepted exception to NFR-M3; owner confirms.
4. **One auth layer between slice 1 and #70.** Until the app verifies the IAP JWT, IAP is the only check. Acceptable because `/healthz` returns only status and version and the other routes do not exist yet. Owner confirms.
5. **Terraform locally.** `terraform validate` in the dev container needs the Terraform registry in `.devcontainer/allowed-domains.txt`, and Terraform in the image (ADR-0009 follow-up). Proposed: add both in this PR if the owner wants local validation; otherwise CI validates only.
6. **Cold-start evidence is manual.** IAP blocks automated calls, so AC15 is measured by the owner's hand-made request and Cloud Run metrics. Owner confirms.

## Out of scope

- The app's JWT check and owner verification (#70) and the A-1 snapshot call (slice 3).
- Worker logic, run queue, any data written to Firestore or the bucket.
- Secret values (added when a slice needs them), email setup (#21), monitoring beyond the budget (#33).
- A second environment, a custom domain, a load balancer.
